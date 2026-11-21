from django.test import SimpleTestCase, TestCase

from .models import StockReturn
from .optimizer import future_value_dca, optimize_portfolio
from .stocks import DEFAULT_RETURNS, SET50_STOCKS


class PortfolioOptimizerTests(SimpleTestCase):
    def test_zero_effective_return_adds_monthly_contributions(self):
        self.assertEqual(future_value_dca(1000, 0, 12), 12000.0)

    def test_positive_return_uses_annuity_due_formula(self):
        monthly_return = (1.12 ** (1 / 12)) - 1
        expected = 1000 * (((1 + monthly_return) ** 12 - 1) / monthly_return) * (1 + monthly_return)
        self.assertAlmostEqual(future_value_dca(1000, 12, 12), expected)

    def test_annuity_due_is_one_month_ahead_of_ordinary_annuity(self):
        monthly_return = (1.12 ** (1 / 12)) - 1
        due = future_value_dca(1000, 12, 12)
        ordinary = due / (1 + monthly_return)
        self.assertGreater(due, ordinary)

    def test_total_loss_returns_zero(self):
        self.assertEqual(future_value_dca(1000, -100, 12), 0.0)

    def test_ga_returns_valid_weights_and_fitness(self):
        result = optimize_portfolio(
            ["ADVANC", "AOT", "BBL"],
            1000,
            12,
            {"ADVANC": 2.0, "AOT": 12.0, "BBL": 5.0},
            ga_params={
                "population_size": 40,
                "generations": 60,
                "seed": 123,
            },
        )
        self.assertAlmostEqual(sum(result["weights"]), 100.0, places=8)
        self.assertTrue(all(0 <= weight <= 100 for weight in result["weights"]))
        self.assertAlmostEqual(
            result["future_value"],
            future_value_dca(1000, result["portfolio_annual_return"], 12),
        )
        self.assertEqual(len(result["fitness_history"]), 61)
        self.assertTrue(
            all(
                result["fitness_history"][i] <= result["fitness_history"][i + 1] + 1e-9
                for i in range(len(result["fitness_history"]) - 1)
            )
        )

    def test_ga_is_reproducible_when_seed_is_set(self):
        args = (
            ["ADVANC", "AOT"],
            1000,
            12,
            {"ADVANC": 1.0, "AOT": 8.0},
        )
        params = {"population_size": 20, "generations": 15, "seed": 7}
        first = optimize_portfolio(*args, ga_params=params)
        second = optimize_portfolio(*args, ga_params=params)
        self.assertEqual(first["weights"], second["weights"])
        self.assertEqual(first["fitness_history"], second["fitness_history"])

    def test_optimizer_rejects_missing_returns(self):
        with self.assertRaisesRegex(ValueError, "Missing annual return"):
            optimize_portfolio(
                ["ADVANC", "AOT"], 1000, 12, {"ADVANC": 1.0},
                ga_params={"population_size": 10, "generations": 5},
            )

    def test_optimizer_rejects_invalid_ga_parameters(self):
        with self.assertRaisesRegex(ValueError, "population_size"):
            optimize_portfolio(
                ["ADVANC", "AOT"], 1000, 12,
                {"ADVANC": 1.0, "AOT": 2.0},
                ga_params={"population_size": 2},
            )

    def test_dca_rejects_invalid_input(self):
        with self.assertRaises(ValueError):
            future_value_dca(1000, -100.01, 12)


class StockApiTests(TestCase):
    def test_stocks_endpoint_returns_all_fifty_defaults(self):
        response = self.client.get("/api/stocks/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["stocks"]), 50)
        self.assertEqual(StockReturn.objects.count(), 50)
        self.assertEqual(DEFAULT_RETURNS["BCH"], 1.0)
        self.assertEqual(len(SET50_STOCKS), 50)

    def test_stock_returns_can_be_saved(self):
        response = self.client.post(
            "/api/stocks/",
            data='{"returns":{"AOT":3.25,"BCH":-2}}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(StockReturn.objects.get(symbol="AOT").annual_return, 3.25)
        self.assertEqual(StockReturn.objects.get(symbol="BCH").annual_return, -2.0)

    def test_stock_returns_reject_symbols_outside_set50(self):
        response = self.client.post(
            "/api/stocks/",
            data='{"returns":{"NOTASET50":3.25}}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_optimize_api_accepts_ga_parameters(self):
        response = self.client.post(
            "/api/optimize/",
            data='{"stocks":["ADVANC","AOT"],"monthly_money":1000,'
                 '"ga_params":{"population_size":10,"generations":5,"seed":1}}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["status"], "running")

    def test_optimize_rejects_non_object_json_payload(self):
        response = self.client.post(
            "/api/optimize/",
            data="[]",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
