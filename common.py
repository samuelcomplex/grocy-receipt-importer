from decimal import Decimal


def money(value):
    return Decimal(value.replace(".", "").replace(",", "."))


def money_str(value):
    return f"{value:.2f}".replace(".", ",")


def quantity(value):
    return Decimal(value.replace(",", "."))
