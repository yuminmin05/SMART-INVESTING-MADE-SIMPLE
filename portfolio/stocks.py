"""รายชื่อ SET50 และค่าเริ่มต้นของผลตอบแทนรายปี"""

SET50_STOCKS = [
    "ADVANC", "AOT", "AWC", "BANPU", "BBL",
    "BCH", "BCP", "BDMS", "BEM", "BGRIM",
    "BH", "BJC", "BTS", "CBG", "CCET",
    "CENTEL", "COM7", "CPALL", "CPF", "CPN",
    "CRC", "DELTA", "EGCO", "GULF", "GPSC",
    "HMPRO", "IVL", "KBANK", "KKP", "KTB",
    "KTC", "LH", "MINT", "MTC", "OR",
    "OSP", "PTT", "PTTEP", "PTTGC", "RATCH",
    "SAWAD", "SCB", "SCC", "SCGP", "TCAP",
    "TIDLOR", "TISCO", "TOP", "TRUE", "WHA",
]

DEFAULT_RETURNS = {
    "ADVANC": 0.4988,
    "AOT": 1.33,
    "AWC": 2.66,
    "BANPU": 2.4938,
    "BBL": 2.9094,
}
DEFAULT_RETURNS.update({symbol: 1.0 for symbol in SET50_STOCKS if symbol not in DEFAULT_RETURNS})


def yahoo_symbol(symbol):
    """แปลงสัญลักษณ์ภายในระบบเป็นสัญลักษณ์หุ้น SET ที่ Yahoo Finance ใช้"""
    if symbol not in SET50_STOCKS:
        raise ValueError(f"ไม่พบสัญลักษณ์หุ้น: {symbol}")
    return f"{symbol}.BK"
