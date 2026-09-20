from apps.api.services import products
from apps.api.services.products import _query, normalize_result
from apps.api.routers.retailer import retailer_redirect
from apps.api.models.schemas import RetailerRedirectRequest


def test_normalize_result_exposes_a_real_retailer_link():
    row = normalize_result(
        {
            "id": "coat-1",
            "title": "Navy blazer",
            "url": "https://retailer.example/products/navy-blazer",
            "content": "Structured navy blazer $89.00",
            "image_url": "https://retailer.example/images/blazer.jpg",
        },
        category="outerwear",
    )

    assert row is not None
    assert row["product_url"] == "https://retailer.example/products/navy-blazer"
    assert row["price_cents"] == 8900
    assert row["rung"] == "NEW"
    assert row["owner_id"] is None


def test_normalize_result_marks_secondhand_items_used():
    row = normalize_result(
        {
            "title": "Pre-owned Oxford shirt",
            "url": "https://shop.example/used/oxford",
            "content": "Pre-owned condition $18",
        },
        category="top",
    )

    assert row is not None
    assert row["rung"] == "USED"


def test_normalize_result_rejects_obvious_editorial_results():
    editorial = {
        "title": "Stock Your Internship Wardrobe with These 16 Best Business Casual Outfits",
        "url": "https://fashion.example/articles/internship-wardrobe",
        "content": "Shop these looks and prices from $89.",
    }

    assert normalize_result(editorial, category="outerwear") is None


def test_normalize_result_rejects_informational_titles_even_without_editorial_path():
    editorial = {
        "title": "What to Wear in an Air Conditioned Office in Summer",
        "url": "https://fashion.example/summer-office",
        "content": "Ideas from $89.",
    }

    assert normalize_result(editorial, category="outerwear") is None


def test_normalize_result_accepts_non_clothing_product_pages():
    row = normalize_result(
        {
            "title": "Two-burner camping stove",
            "url": "https://outdoor.example/shop/two-burner-stove",
            "content": "Portable stove, $64.99",
        },
        category="cooking equipment",
    )

    assert row is not None
    assert row["product_url"] == "https://outdoor.example/shop/two-burner-stove"
    assert row["price_cents"] == 6499


def test_query_biases_toward_direct_purchase_pages():
    query = _query(
        "camping trip",
        {"label": "cook hot food", "attrs": {"capacity": "two people"}},
    )

    assert "direct product page" in query
    assert "buy now" in query
    assert "current price" in query


def test_normalize_result_uses_need_attrs_for_live_results_without_attrs():
    row = normalize_result(
        {
            "title": "Navy blazer",
            "url": "https://retailer.example/products/navy-blazer",
            "content": "Structured navy blazer $89.00",
        },
        category="outerwear",
        need_attrs={"formality": "business-casual", "warmth": "medium"},
    )

    assert row is not None
    assert row["attrs"] == {"formality": "business-casual", "warmth": "medium"}


def test_fetch_products_scopes_need_attrs_to_each_live_search(monkeypatch):
    monkeypatch.setattr(products, "demo_mode_enabled", lambda: False)
    monkeypatch.setattr(
        products,
        "_request",
        lambda query: [
            {
                "title": "Navy blazer",
                "url": "https://retailer.example/products/navy-blazer",
                "content": "$89",
            }
        ],
    )

    rows = products.fetch_products(
        "business casual",
        [
            {
                "id": "need-1",
                "category": "outerwear",
                "attrs": {"formality": "business-casual", "warmth": "medium"},
            }
        ],
    )

    assert len(rows) == 1
    assert rows[0]["category"] == "outerwear"
    assert rows[0]["attrs"] == {"formality": "business-casual", "warmth": "medium"}


def test_normalize_result_rejects_results_without_buyable_data():
    assert normalize_result(
        {"title": "Navy blazer", "url": "https://retailer.example/blazer"},
        category="outerwear",
    ) is None


def test_retailer_redirect_returns_external_destination():
    response = retailer_redirect(
        RetailerRedirectRequest(product_url="https://shop.example/item")
    )

    assert response.product_url == "https://shop.example/item"
    assert response.retailer == "shop.example"
    assert normalize_result(
        {"title": "Navy blazer", "content": "$89"},
        category="outerwear",
    ) is None
