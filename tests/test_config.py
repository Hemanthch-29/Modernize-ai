"""Config loads portfolio.yaml and resolves repos/databases."""
from modernizer.config import load_portfolio


def test_portfolio_applications_and_shared_database():
    portfolio = load_portfolio()

    names = {app.name for app in portfolio.applications}
    assert {"OnlineShop", "Reporting"} <= names

    online_shop = portfolio.application("OnlineShop")
    assert online_shop is not None
    assert online_shop.wave == 2
    assert {r.name for r in online_shop.repos} == {"shop-ui", "shop-api"}

    # ShopDB is listed under both apps but de-duplicated to a single entry.
    databases = portfolio.databases()
    assert [db.name for db in databases] == ["ShopDB"]
    assert databases[0].connection_env == "SHOPDB_CONN"


def test_repo_abs_path_points_into_sample_legacy():
    portfolio = load_portfolio()
    shop_api = next(r for r in portfolio.repos() if r.name == "shop-api")

    assert shop_api.abs_path.name == "shop-api"
    assert shop_api.abs_path.exists()
