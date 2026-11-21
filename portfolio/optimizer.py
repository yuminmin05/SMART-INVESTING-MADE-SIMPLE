"""Genetic Algorithm optimizer for monthly DCA portfolio allocation."""
import math
import random


def future_value_dca(monthly_payment, annual_return, months):
    """Future value of beginning-of-month DCA contributions (annuity due).

    annual_return is an effective annual percentage return.
    """
    if isinstance(monthly_payment, bool) or not isinstance(monthly_payment, (int, float)):
        raise ValueError("monthly_payment must be a finite positive number")
    if not math.isfinite(monthly_payment) or monthly_payment <= 0:
        raise ValueError("monthly_payment must be a finite positive number")
    if isinstance(annual_return, bool) or not isinstance(annual_return, (int, float)):
        raise ValueError("annual_return must be between -100 and 1,000 percent")
    if not math.isfinite(annual_return) or not -100 <= annual_return <= 1000:
        raise ValueError("annual_return must be between -100 and 1,000 percent")
    if isinstance(months, bool) or not isinstance(months, int) or months <= 0:
        raise ValueError("months must be a positive integer")

    if annual_return == -100:
        return 0.0

    monthly_return = math.expm1(math.log1p(annual_return / 100) / 12)
    if monthly_return == 0:
        return float(monthly_payment * months)

    try:
        # Annuity Due: each monthly contribution is invested at the start
        # of its month, hence the additional (1 + monthly_return) factor.
        growth_sum = math.expm1(months * math.log1p(monthly_return)) / monthly_return
        future_value = monthly_payment * growth_sum * (1 + monthly_return)
    except OverflowError as error:
        raise ValueError("The requested DCA projection exceeds the numeric range") from error
    if not math.isfinite(future_value):
        raise ValueError("The requested DCA projection exceeds the numeric range")
    return float(future_value)



def _normalize_weights(weights, max_weight=0.60):
    """
    Normalize weights ให้รวมกันเป็น 100%
    และจำกัดน้ำหนักหุ้นแต่ละตัวไม่เกิน 60%
    """
    if not weights:
        raise ValueError("At least one gene is required")

    n = len(weights)

    if max_weight < 1.0 / n or max_weight > 1.0:
        raise ValueError("Invalid maximum weight")

    values = [max(0.0, float(w)) for w in weights]

    # ป้องกันกรณีค่าน้ำหนักทุกตัวเป็น 0
    if sum(values) <= 1e-15:
        return [1.0 / n] * n

    # ป้องกันกรณีมียีนบางตัวเป็น 0
    values = [max(w, 1e-12) for w in values]

    # หา scale factor ด้วย Binary Search
    low = 0.0
    high = 1.0

    while sum(min(w * high, max_weight) for w in values) < 1.0:
        high *= 2.0

    for _ in range(100):
        mid = (low + high) / 2

        total = sum(
            min(w * mid, max_weight)
            for w in values
        )

        if total < 1.0:
            low = mid
        else:
            high = mid

    result = [
        min(w * high, max_weight)
        for w in values
    ]

    return result


def _validate_ga_params(ga_params):
    params = {
        "population_size": 60,
        "generations": 100,
        "crossover_prob": 0.9,
        "mutation_rate": 0.1,
        "mutation_sigma": 0.05,
        "eta_c": 20.0,
        "tournament_size": 3,
        "elite_size": 2,
        "seed": None,
    }
    if ga_params is not None:
        if not isinstance(ga_params, dict):
            raise ValueError("ga_params must be an object")
        unknown = set(ga_params) - set(params)
        if unknown:
            raise ValueError(f"Unsupported GA parameters: {', '.join(sorted(unknown))}")
        params.update(ga_params)

    for key in ("population_size", "generations", "tournament_size", "elite_size"):
        value = params[key]
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{key} must be an integer")
    if params["population_size"] < 4 or params["population_size"] > 500:
        raise ValueError("population_size must be between 4 and 500")
    if params["generations"] < 1 or params["generations"] > 1000:
        raise ValueError("generations must be between 1 and 1,000")
    if not 2 <= params["tournament_size"] <= params["population_size"]:
        raise ValueError("tournament_size must be between 2 and population_size")
    if not 1 <= params["elite_size"] < params["population_size"]:
        raise ValueError("elite_size must be between 1 and population_size - 1")

    for key, low, high in (
        ("crossover_prob", 0.0, 1.0),
        ("mutation_rate", 0.0, 1.0),
        ("mutation_sigma", 0.0, 1.0),
        ("eta_c", 1.0, 100.0),
    ):
        value = params[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{key} must be numeric")
        if not math.isfinite(value) or not low <= value <= high:
            raise ValueError(f"{key} must be between {low} and {high}")
        params[key] = float(value)

    if params["seed"] is not None:
        if isinstance(params["seed"], bool) or not isinstance(params["seed"], int):
            raise ValueError("seed must be an integer or null")
    return params


def _sbx_crossover(parent1, parent2, eta_c, rng):
    """Simulated Binary Crossover (SBX), returning two children."""
    child1, child2 = [], []
    for x1, x2 in zip(parent1, parent2):
        if rng.random() > 0.5 or abs(x1 - x2) < 1e-14:
            child1.append(x1)
            child2.append(x2)
            continue
        low, high = min(x1, x2), max(x1, x2)
        rand = rng.random()

        beta = 1.0 + (2.0 * low) / (high - low)
        alpha = 2.0 - beta ** (-(eta_c + 1.0))
        if rand <= 1.0 / alpha:
            beta_q = (rand * alpha) ** (1.0 / (eta_c + 1.0))
        else:
            beta_q = (1.0 / (2.0 - rand * alpha)) ** (1.0 / (eta_c + 1.0))
        c1 = 0.5 * ((low + high) - beta_q * (high - low))

        beta = 1.0 + (2.0 * (1.0 - high)) / (high - low)
        alpha = 2.0 - beta ** (-(eta_c + 1.0))
        if rand <= 1.0 / alpha:
            beta_q = (rand * alpha) ** (1.0 / (eta_c + 1.0))
        else:
            beta_q = (1.0 / (2.0 - rand * alpha)) ** (1.0 / (eta_c + 1.0))
        c2 = 0.5 * ((low + high) + beta_q * (high - low))

        if rng.random() <= 0.5:
            c1, c2 = c2, c1
        child1.append(min(1.0, max(0.0, c1)))
        child2.append(min(1.0, max(0.0, c2)))
    return _normalize_weights(child1), _normalize_weights(child2)


def _tournament_select(population, fitnesses, tournament_size, rng):
    candidates = rng.sample(range(len(population)), tournament_size)
    winner = max(candidates, key=lambda index: fitnesses[index])
    return population[winner][:]


def _mutate(chromosome, mutation_rate, mutation_sigma, rng):
    mutated = chromosome[:]
    for index in range(len(mutated)):
        if rng.random() < mutation_rate:
            mutated[index] += rng.gauss(0.0, mutation_sigma)
    return _normalize_weights(mutated)


def optimize_portfolio(
    selected_stocks,
    monthly_money,
    months,
    stock_returns,
    ga_params=None,
):
    """Find a high-FV allocation using GA and an annuity-due fitness function.

    A chromosome contains one non-negative allocation weight per selected stock.
    The normalized weights sum to 1.0; fitness is the annuity-due FV of the
    monthly payment under the weighted portfolio effective annual return.
    """
    if (
        not isinstance(selected_stocks, (list, tuple))
        or not selected_stocks
        or any(not isinstance(stock, str) or not stock for stock in selected_stocks)
    ):
        raise ValueError("At least one stock is required")
    if len(selected_stocks) != len(set(selected_stocks)):
        raise ValueError("Selected stocks must be unique")
    if len(selected_stocks) < 2:
        raise ValueError("At least two stocks are required")

    for stock in selected_stocks:
        if stock not in stock_returns:
            raise ValueError(f"Missing annual return for {stock}")
        value = stock_returns[stock]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"Invalid annual return for {stock}")
        if not math.isfinite(value) or not -100 <= value <= 1000:
            raise ValueError(f"Invalid annual return for {stock}")

    params = _validate_ga_params(ga_params)
    rng = random.Random(params["seed"])
    stock_rate = [float(stock_returns[stock]) for stock in selected_stocks]
    dimension = len(selected_stocks)

    def evaluate(chromosome):
        portfolio_annual_return = sum(
            weight * annual_return
            for weight, annual_return in zip(chromosome, stock_rate)
        )
        fv = future_value_dca(monthly_money, portfolio_annual_return, months)
        return fv, portfolio_annual_return

    population = [
        _normalize_weights([rng.random() for _ in range(dimension)])
        for _ in range(params["population_size"])
    ]
    fitness_history = []
    best_chromosome = None
    best_fitness = float("-inf")
    best_return = 0.0

    for _generation in range(params["generations"]):
        evaluated = [evaluate(chromosome) for chromosome in population]
        fitnesses = [item[0] for item in evaluated]
        generation_best_index = max(range(len(population)), key=lambda i: fitnesses[i])
        if fitnesses[generation_best_index] > best_fitness:
            best_fitness = fitnesses[generation_best_index]
            best_chromosome = population[generation_best_index][:]
            best_return = evaluated[generation_best_index][1]
        fitness_history.append(float(best_fitness))

        ranked = sorted(
            range(len(population)),
            key=lambda index: fitnesses[index],
            reverse=True,
        )
        next_population = [
            population[index][:]
            for index in ranked[:params["elite_size"]]
        ]

        while len(next_population) < params["population_size"]:
            parent1 = _tournament_select(
                population, fitnesses, params["tournament_size"], rng
            )
            parent2 = _tournament_select(
                population, fitnesses, params["tournament_size"], rng
            )
            if rng.random() < params["crossover_prob"]:
                child1, child2 = _sbx_crossover(
                    parent1, parent2, params["eta_c"], rng
                )
            else:
                child1, child2 = parent1[:], parent2[:]
            child1 = _mutate(
                child1, params["mutation_rate"], params["mutation_sigma"], rng
            )
            child2 = _mutate(
                child2, params["mutation_rate"], params["mutation_sigma"], rng
            )
            next_population.append(child1)
            if len(next_population) < params["population_size"]:
                next_population.append(child2)
        population = next_population

    # Include the final generation in the best-so-far record.
    evaluated = [evaluate(chromosome) for chromosome in population]
    final_index = max(range(len(population)), key=lambda i: evaluated[i][0])
    if evaluated[final_index][0] > best_fitness:
        best_fitness = evaluated[final_index][0]
        best_chromosome = population[final_index][:]
        best_return = evaluated[final_index][1]
    fitness_history.append(float(best_fitness))

    weights_percent = [weight * 100.0 for weight in best_chromosome]
    # Correct floating point drift so the displayed total is exactly 100%.
    if weights_percent:
        weights_percent[-1] += 100.0 - sum(weights_percent)

    best_stock = (
        selected_stocks[weights_percent.index(max(weights_percent))]
        if max(weights_percent) >= 99.999999
        else None
    )
    return {
        "weights": weights_percent,
        "future_value": float(best_fitness),
        "best_stock": best_stock,
        "portfolio_annual_return": float(best_return),
        "fitness_history": fitness_history,
        "generations": params["generations"],
        "ga_params": {key: value for key, value in params.items() if key != "seed"},
    }
