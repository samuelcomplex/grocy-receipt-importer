from decimal import Decimal

from common import quantity
from app.grocy import (
    create_product,
    load_quantity_unit_conversions,
    update_quantity_unit_conversion,
)
from app.product_matching import normalize_product_name


def validate_new_product_configuration(
    name,
    location_id,
    purchase_unit_id,
    stock_unit_id,
    conversion_factor,
    products,
    locations,
    quantity_units,
):
    # Use the same payload validation that actual creation uses.
    product_payload = build_new_product_payload(
        name=name,
        location_id=location_id,
        purchase_unit_id=purchase_unit_id,
        stock_unit_id=stock_unit_id,
        conversion_factor=conversion_factor,
    )

    location_ids = {
        str(location.get("id"))
        for location in locations
    }

    if str(location_id) not in location_ids:
        raise ValueError(
            "Selected location no longer exists in Grocy."
        )

    quantity_unit_ids = {
        str(unit.get("id"))
        for unit in quantity_units
    }

    if str(purchase_unit_id) not in quantity_unit_ids:
        raise ValueError(
            "Selected purchase unit no longer exists in Grocy."
        )

    if str(stock_unit_id) not in quantity_unit_ids:
        raise ValueError(
            "Selected stock unit no longer exists in Grocy."
        )

    normalized_name = normalize_product_name(name)

    if not normalized_name:
        raise ValueError("Product name is required.")

    for product in products:
        if normalize_product_name(product.get("name", "")) == normalized_name:
            raise ValueError(
                "A Grocy product with this name already exists. "
                "Please select the existing product instead."
            )

    return product_payload


def build_new_product_payload(
    name,
    location_id,
    purchase_unit_id,
    stock_unit_id,
    conversion_factor,
):
    if not name or not name.strip():
        raise ValueError("Product name is required.")

    if not location_id:
        raise ValueError("Product location is required.")

    if not purchase_unit_id:
        raise ValueError("Purchase quantity unit is required.")

    if not stock_unit_id:
        raise ValueError("Stock quantity unit is required.")

    try:
        conversion = Decimal(str(conversion_factor))
    except Exception as exc:
        raise ValueError("Conversion factor must be a number.") from exc

    if conversion <= 0:
        raise ValueError("Conversion factor must be greater than zero.")

    return {
        "name": name.strip(),
        "location_id": int(location_id),
        "qu_id_purchase": int(purchase_unit_id),
        "qu_id_stock": int(stock_unit_id),
        "qu_id_consume": int(stock_unit_id),
        "qu_id_price": int(purchase_unit_id),
        "min_stock_amount": 0,
    }


def calculate_price_per_stock_unit(net_price, stock_amount):
    if net_price is None:
        raise ValueError("Receipt item has no net price.")

    try:
        price = Decimal(str(net_price))
        amount = Decimal(str(stock_amount))
    except Exception as exc:
        raise ValueError("Receipt price or stock amount is invalid.") from exc

    if amount <= 0:
        raise ValueError("Stock amount must be greater than zero.")

    return price / amount


def calculate_stock_amount(
    purchase_amount,
    purchase_unit_id,
    stock_unit_id,
    conversions,
    product_id=None,
    conversion_factor=None,
):
    amount = quantity(purchase_amount)

    if int(purchase_unit_id) == int(stock_unit_id):
        factor = Decimal("1")
    elif conversion_factor is not None:
        factor = Decimal(str(conversion_factor))
        if factor <= 0:
            raise ValueError(
                "Conversion factor must be greater than zero."
            )
    else:
        factor = purchase_to_stock_factor(
            purchase_unit_id,
            stock_unit_id,
            conversions,
            product_id=product_id,
        )

    return amount * factor


def create_new_grocy_product(
    product_payload,
    purchase_unit_id,
    stock_unit_id,
    conversion_factor,
):
    created = create_product(product_payload)

    product_id = created.get("created_object_id")

    if product_id is None:
        product_id = created.get("id")

    if product_id is None:
        raise RuntimeError(
            "Grocy created the product but did not return its product ID."
        )

    product_id = int(product_id)
    purchase_unit_id = int(purchase_unit_id)
    stock_unit_id = int(stock_unit_id)

    try:
        desired_factor = Decimal(str(conversion_factor))
    except Exception as exc:
        raise ValueError("Conversion factor must be a number.") from exc

    if desired_factor <= 0:
        raise ValueError("Conversion factor must be greater than zero.")

    if purchase_unit_id != stock_unit_id:
        conversions = load_quantity_unit_conversions()

        conversion_result = find_purchase_to_stock_conversion(
            purchase_unit_id,
            stock_unit_id,
            conversions,
            product_id=product_id,
        )

        if conversion_result is None:
            raise RuntimeError(
                "Grocy created the product but did not create its "
                "purchase-to-stock conversion."
            )

        conversion = conversion_result["conversion"]
        conversion_id = conversion.get("id")

        if conversion_id is None:
            raise RuntimeError(
                "Grocy purchase-to-stock conversion did not return its ID."
            )

        update_quantity_unit_conversion(
            conversion_id,
            {
                "from_qu_id": purchase_unit_id,
                "to_qu_id": stock_unit_id,
                "factor": float(desired_factor),
                "product_id": product_id,
            },
        )

    return {
        "product_id": product_id,
        "product": created,
        "conversion_factor": str(desired_factor),
    }


def find_purchase_to_stock_conversion(
    purchase_unit_id,
    stock_unit_id,
    conversions,
    product_id=None,
):
    purchase_id = int(purchase_unit_id)
    stock_id = int(stock_unit_id)

    if purchase_id == stock_id:
        return {
            "factor": Decimal("1"),
            "conversion": None,
        }

    candidates = []

    for conversion in conversions:
        if int(conversion.get("from_qu_id", 0)) != purchase_id:
            continue

        if int(conversion.get("to_qu_id", 0)) != stock_id:
            continue

        conversion_product_id = conversion.get("product_id")

        if product_id is not None:
            if (
                conversion_product_id is not None
                and int(conversion_product_id) == int(product_id)
            ):
                candidates.append(conversion)
        elif conversion_product_id is None:
            candidates.append(conversion)

    if not candidates:
        return None

    if len(candidates) > 1:
        raise ValueError(
            "Multiple purchase-to-stock conversions match the selected quantity units."
        )

    conversion = candidates[0]

    try:
        factor = Decimal(str(conversion["factor"]))
    except Exception as exc:
        raise ValueError("Grocy conversion factor is invalid.") from exc

    if factor <= 0:
        raise ValueError("Grocy conversion factor must be greater than zero.")

    return {
        "factor": factor,
        "conversion": conversion,
    }


def purchase_to_stock_factor(
    purchase_unit_id,
    stock_unit_id,
    conversions,
    product_id=None,
):
    result = find_purchase_to_stock_conversion(
        purchase_unit_id,
        stock_unit_id,
        conversions,
        product_id=product_id,
    )

    if result is None:
        raise ValueError(
            "No purchase-to-stock conversion exists for the selected quantity units."
        )

    return result["factor"]
