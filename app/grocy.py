import requests

from app.config import GROCY_API_KEY, GROCY_BASE_URL


def headers():
    return {
        "GROCY-API-KEY": GROCY_API_KEY,
        "Accept": "application/json",
    }


def grocy_request(method, path, payload=None, expect_json=True):
    request_headers = headers()

    if payload is not None:
        request_headers["Content-Type"] = "application/json"

    response = requests.request(
        method,
        GROCY_BASE_URL + path,
        headers=request_headers,
        json=payload,
        timeout=20,
    )

    if not response.ok:
        raise requests.HTTPError(
            f"{response.status_code} {response.reason}: {response.text}",
            response=response,
        )

    if expect_json:
        return response.json()


def grocy_get(path):
    return grocy_request("GET", path)


def grocy_post(path, payload):
    return grocy_request("POST", path, payload)


def grocy_post_no_content(path, payload):
    grocy_request("POST", path, payload, expect_json=False)


def grocy_put(path, payload):
    return grocy_request("PUT", path, payload)


def load_products():
    return grocy_get("/api/objects/products")


def load_product(product_id):
    return grocy_get(f"/api/objects/products/{int(product_id)}")


def load_locations():
    return grocy_get("/api/objects/locations")


def load_quantity_units():
    return grocy_get("/api/objects/quantity_units")


def load_quantity_unit_conversions():
    return grocy_get("/api/objects/quantity_unit_conversions")


def create_product(payload):
    return grocy_post("/api/objects/products", payload)


def create_quantity_unit_conversion(payload):
    return grocy_post("/api/objects/quantity_unit_conversions", payload)


def update_quantity_unit_conversion(conversion_id, payload):
    return grocy_put(
        f"/api/objects/quantity_unit_conversions/{int(conversion_id)}",
        payload,
    )
