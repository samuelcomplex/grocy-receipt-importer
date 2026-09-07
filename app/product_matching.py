from __future__ import annotations

import difflib
import re


def normalize_product_name(value):
    value = value.lower().strip()
    value = re.sub(
        r"[^a-z0-9åäöéèüæø]+",
        " ",
        value,
    )
    return re.sub(r"\s+", " ", value).strip()


def product_name_tokens(value):
    return {
        token
        for token in normalize_product_name(value).split()
        if token
    }


def token_match_score(receipt_name, product_name):
    receipt_tokens = product_name_tokens(receipt_name)
    product_tokens = product_name_tokens(product_name)

    if not receipt_tokens or not product_tokens:
        return 0.0

    shared = receipt_tokens & product_tokens

    receipt_coverage = len(shared) / len(receipt_tokens)
    product_coverage = len(shared) / len(product_tokens)

    return (receipt_coverage + product_coverage) / 2


def suggest_product_matches(items, products):
    normalized_products = [
        (
            product,
            normalize_product_name(product.get("name", "")),
        )
        for product in products
        if product.get("name")
    ]

    for item in items:
        if item.get("kind") != "product":
            continue

        if item.get("grocy_product_id"):
            item["match_type"] = "saved"
            continue

        description = normalize_product_name(
            item.get("description", "")
        )

        if not description:
            continue

        exact = next(
            (
                product
                for product, normalized_name in normalized_products
                if normalized_name == description
            ),
            None,
        )

        if exact:
            item["suggested_grocy_product_id"] = exact["id"]
            item["suggested_grocy_product_name"] = exact["name"]
            item["match_score"] = 1.0
            item["match_type"] = "exact"
            continue

        token_candidates = []

        for product, normalized_name in normalized_products:
            score = token_match_score(description, normalized_name)

            if score >= 0.50:
                token_candidates.append(
                    (score, product, normalized_name)
                )

        if token_candidates:
            token_candidates.sort(
                key=lambda candidate: candidate[0],
                reverse=True,
            )

            best_score, best_product, _ = token_candidates[0]

            second_score = (
                token_candidates[1][0]
                if len(token_candidates) > 1
                else 0.0
            )

            if best_score >= 0.70 and (
                len(token_candidates) == 1
                or best_score - second_score >= 0.10
            ):
                item["suggested_grocy_product_id"] = best_product["id"]
                item["suggested_grocy_product_name"] = best_product["name"]
                item["match_score"] = round(best_score, 2)
                item["match_type"] = "token"
                continue

            if len(token_candidates) > 1:
                continue

        fuzzy_candidates = []

        for product, normalized_name in normalized_products:
            score = difflib.SequenceMatcher(
                None,
                description,
                normalized_name,
            ).ratio()

            if score >= 0.70:
                fuzzy_candidates.append((score, product))

        if fuzzy_candidates:
            fuzzy_candidates.sort(
                key=lambda candidate: candidate[0],
                reverse=True,
            )

            best_score, best_product = fuzzy_candidates[0]

            second_score = (
                fuzzy_candidates[1][0]
                if len(fuzzy_candidates) > 1
                else 0.0
            )

            if best_score >= 0.70 and (
                len(fuzzy_candidates) == 1
                or best_score - second_score >= 0.10
            ):
                item["suggested_grocy_product_id"] = best_product["id"]
                item["suggested_grocy_product_name"] = best_product["name"]
                item["match_score"] = round(best_score, 2)
                item["match_type"] = "suggested"
