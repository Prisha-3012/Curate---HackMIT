from apps.api.services.products import normalize_result
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
