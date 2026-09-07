import requests

from app.config import GROCY_API_KEY, GROCY_BASE_URL


def headers():
    return {
        "GROCY-API-KEY": GROCY_API_KEY,
        "Accept": "application/json",
    }


def grocy_get(path):
    response = requests.get(
        GROCY_BASE_URL + path,
        headers=headers(),
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def grocy_post(path, payload):
    response = requests.post(
        GROCY_BASE_URL + path,
        headers={
            **headers(),
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=20,
    )
    if not response.ok:
        raise requests.HTTPError(
            f"{response.status_code} {response.reason}: {response.text}",
            response=response,
        )
    return response.json()


def grocy_post_no_content(path, payload):
    response = requests.post(
        GROCY_BASE_URL + path,
        headers={
            **headers(),
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=20,
    )
    response.raise_for_status()


def grocy_put(path, payload):
    response = requests.put(
        GROCY_BASE_URL + path,
        headers={
            **headers(),
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=20,
    )
    if not response.ok:
        raise requests.HTTPError(
            f"{response.status_code} {response.reason}: {response.text}",
            response=response,
        )
    return response.json()


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
