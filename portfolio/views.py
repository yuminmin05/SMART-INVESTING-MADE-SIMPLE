"""หน้าเว็บ API และ background worker สำหรับการคำนวณพอร์ต"""
import json
import math
import threading
import uuid

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from .optimizer import optimize_portfolio, _validate_ga_params
from .models import StockReturn
from .stocks import DEFAULT_RETURNS, SET50_STOCKS

YEARS = (1, 5, 10)
JOBS = {}
JOBS_LOCK = threading.Lock()


def index(request):
    return render(request, "portfolio/index.html")


def _ensure_stock_rows():
    for symbol in SET50_STOCKS:
        StockReturn.objects.get_or_create(
            symbol=symbol, defaults={"annual_return": DEFAULT_RETURNS[symbol]}
        )


@require_GET
def stocks_api(request):
    _ensure_stock_rows()
    stocks = list(
        StockReturn.objects.filter(symbol__in=SET50_STOCKS)
        .values("symbol", "annual_return")
        .order_by("symbol")
    )
    return JsonResponse({"stocks": stocks})


@require_POST
def save_stock_returns_api(request):
    try:
        payload = json.loads(request.body)
        returns = payload.get("returns")
        if not isinstance(returns, dict):
            raise ValueError("กรุณาส่งข้อมูลผลตอบแทนในรูปแบบที่ถูกต้อง")
        invalid = [symbol for symbol in returns if symbol not in SET50_STOCKS]
        if invalid:
            raise ValueError("พบสัญลักษณ์หุ้นที่ไม่อยู่ใน SET50")
        validated = {}
        for symbol, value in returns.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"ผลตอบแทนของ {symbol} ต้องเป็นตัวเลข")
            if not math.isfinite(value) or value < -100 or value > 1000:
                raise ValueError(f"ผลตอบแทนของ {symbol} ต้องอยู่ระหว่าง -100 ถึง 1,000%")
            validated[symbol] = float(value)
    except (json.JSONDecodeError, ValueError, AttributeError) as error:
        return JsonResponse({"error": str(error) or "ข้อมูลไม่ถูกต้อง"}, status=400)

    _ensure_stock_rows()
    for symbol, value in validated.items():
        StockReturn.objects.filter(symbol=symbol).update(annual_return=value)
    return JsonResponse({"message": "บันทึกผลตอบแทนเรียบร้อย", "updated": len(validated)})


def stocks_api_dispatch(request):
    """แยกการอ่านและบันทึกผลตอบแทนภายใต้ endpoint เดียว"""
    if request.method == "GET":
        return stocks_api(request)
    if request.method == "POST":
        return save_stock_returns_api(request)
    return JsonResponse({"error": "Method not allowed"}, status=405)


def _validate_optimize_payload(request):
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ValueError("ข้อมูลที่ส่งมาไม่ใช่ JSON ที่ถูกต้อง")
    if not isinstance(payload, dict):
        raise ValueError("ข้อมูลที่ส่งมาต้องเป็น JSON object")
    stocks = payload.get("stocks")
    if not isinstance(stocks, list) or any(not isinstance(item, str) for item in stocks):
        raise ValueError("กรุณาเลือกหุ้น SET50 อย่างน้อย 2 ตัว")
    normalized_stocks = [item.strip().upper() for item in stocks]
    if len(normalized_stocks) != len(set(normalized_stocks)):
        raise ValueError("ไม่สามารถเลือกหุ้นซ้ำได้")
    if len(normalized_stocks) < 2:
        raise ValueError("กรุณาเลือกหุ้นอย่างน้อย 2 ตัว")
    if any(symbol not in SET50_STOCKS for symbol in normalized_stocks):
        raise ValueError("เลือกได้เฉพาะหุ้นที่อยู่ใน SET50")

    monthly_money = payload.get("monthly_money")
    if isinstance(monthly_money, bool) or not isinstance(monthly_money, (int, float)):
        raise ValueError("กรุณากรอกเงินลงทุนต่อเดือนเป็นตัวเลข")
    if not math.isfinite(monthly_money) or monthly_money <= 0 or monthly_money > 1_000_000_000:
        raise ValueError("เงินลงทุนต่อเดือนต้องมากกว่า 0 และไม่เกิน 1,000,000,000 บาท")

    ga_params = payload.get("ga_params")
    validated_ga_params = _validate_ga_params(ga_params)
    return normalized_stocks, float(monthly_money), validated_ga_params


def _run_job(job_id, stocks, monthly_money, stock_returns, ga_params):
    try:
        results = {} 
        for years in YEARS:
            with JOBS_LOCK:
                JOBS[job_id]["current_year"] = years
            outcome = optimize_portfolio(
                selected_stocks=stocks,
                monthly_money=monthly_money,
                months=years * 12,
                stock_returns=stock_returns,
                ga_params=ga_params,
            )
            total_investment = monthly_money * years * 12
            results[str(years)] = {
                "years": years,
                "weights": outcome["weights"],
                "fv": outcome["future_value"],
                "total_investment": total_investment,
                "profit": outcome["future_value"] - total_investment,
                "portfolio_annual_return": outcome["portfolio_annual_return"],
                "fitness_history": outcome["fitness_history"],
                "generations": outcome["generations"],
                "ga_params": outcome["ga_params"],
                "best_stock": outcome["best_stock"],
            }
            with JOBS_LOCK:
                JOBS[job_id]["results"] = dict(results)
                JOBS[job_id]["completed_years"] = len(results)
        best_years = max(YEARS, key=lambda years: results[str(years)]["profit"])
        with JOBS_LOCK:
            JOBS[job_id].update(
                {
                    "status": "completed",
                    "results": results,
                    "best_years": best_years,
                    "stocks": stocks,
                    "monthly_money": monthly_money,
                }
            )
    except Exception as error:
        with JOBS_LOCK:
            JOBS[job_id].update({"status": "failed", "error": str(error)})


@require_POST
def optimize_api(request):
    try:
        stocks, monthly_money, ga_params = _validate_optimize_payload(request)
        _ensure_stock_rows()
        stock_returns = {
            item.symbol: item.annual_return
            for item in StockReturn.objects.filter(symbol__in=stocks)
        }
    except ValueError as error:
        return JsonResponse({"error": str(error)}, status=400)

    job_id = uuid.uuid4()
    with JOBS_LOCK:
        JOBS[str(job_id)] = {
            "job_id": str(job_id),
            "status": "running",
            "current_year": YEARS[0],
            "completed_years": 0,
            "results": {},
            "algorithm": "Genetic Algorithm",
        }
    thread = threading.Thread(
        target=_run_job,
        args=(str(job_id), stocks, monthly_money, stock_returns, ga_params),
        daemon=True,
    )
    thread.start()
    return JsonResponse({"job_id": str(job_id), "status": "running"}, status=202)


@require_GET
def optimization_status_api(request, job_id):
    with JOBS_LOCK:
        job = JOBS.get(str(job_id))
        if job is None:
            return JsonResponse({"error": "ไม่พบงานคำนวณนี้"}, status=404)
        return JsonResponse(job)
