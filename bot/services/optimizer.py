import itertools
from typing import Dict, List, Optional
from utils.helpers import calculate_unit_price


class ShoppingOptimizer:
    def __init__(self, user_cart: List[Dict], market_cache: List[List[Dict]]):
        self.user_cart = user_cart
        # Flattening the cache into a single list of products
        self.market_data = [p for sublist in market_cache for p in sublist]
        self.ignore_words = {
            "pilos",
            "саяна",
            "lidl",
            "kaufland",
            "billa",
            "боженци",
            "vereia",
            "верея",
            "myprice",
        }

    def _get_match_score(self, name_a: str, name_b: str) -> int:
        """Calculates how many significant keywords match between two product names."""
        words_a = set(
            w
            for w in name_a.lower().split()
            if w not in self.ignore_words and len(w) > 2
        )
        words_b = set(
            w
            for w in name_b.lower().split()
            if w not in self.ignore_words and len(w) > 2
        )
        return len(words_a.intersection(words_b))

    def _find_best_alternative(self, item: Dict) -> Dict:
        """Finds the best alternative, protecting brand integrity if difference is small."""
        curr_name = item.get("name", "")
        curr_price = float(item.get("price_eur") or item.get("price", 0))
        curr_unit_price, _ = calculate_unit_price(
            curr_price, item.get("unit") or item.get("quantity")
        )

        best_deal = {
            "name": curr_name,
            "price": curr_price,
            "store": item.get("store")
            or item.get("supermarket", {}).get("name", "Unknown"),
            "unit": item.get("unit") or item.get("quantity"),
            "unit_price": curr_unit_price or float("inf"),
            "is_better": False,
        }

        if not curr_unit_price:
            return best_deal

        for p in self.market_data:
            p_name = p.get("name", "")
            if self._get_match_score(curr_name, p_name) >= 2:
                try:
                    p_price = float(p.get("price_eur") or p.get("price", 0))
                    p_unit = p.get("quantity") or p.get("unit")
                    p_u_price, _ = calculate_unit_price(p_price, p_unit)

                    if p_u_price:
                        # MASTER-CLASS BRAND PROTECTION:
                        # Only suggest swap if it's the SAME BRAND or significantly cheaper (>15%)
                        is_same_brand = any(
                            word in curr_name.lower() and word in p_name.lower()
                            for word in ["pilos", "vereia", "верея", "саяна"]
                        )

                        if (
                            not is_same_brand
                            and p_u_price >= best_deal["unit_price"] * 0.85
                        ):
                            continue

                        if p_u_price < best_deal["unit_price"]:
                            best_deal.update(
                                {
                                    "name": p_name,
                                    "price": p_price,
                                    "store": p.get("supermarket", {}).get("name")
                                    if isinstance(p.get("supermarket"), dict)
                                    else p.get("store", "Unknown"),
                                    "unit": p_unit,
                                    "unit_price": p_u_price,
                                    "is_better": True,
                                }
                            )
                except (ValueError, TypeError):
                    continue
        return best_deal

    def get_smart_split_plan(self) -> Dict:
        """Strategy to save the most by visiting multiple stores."""
        plan = {
            "total_original": 0.0,
            "total_optimized": 0.0,
            "savings": 0.0,
            "stores": {},
        }

        for item in self.user_cart:
            orig_price = float(item.get("price_eur") or item.get("price", 0))
            plan["total_original"] += orig_price

            best = self._find_best_alternative(item)
            plan["total_optimized"] += best["price"]

            store_name = best["store"]
            if store_name not in plan["stores"]:
                plan["stores"][store_name] = []
            plan["stores"][store_name].append(best)

        plan["savings"] = round(plan["total_original"] - plan["total_optimized"], 2)
        plan["total_optimized"] = round(plan["total_optimized"], 2)
        return plan

    def get_single_store_plan(self) -> Dict:
        unique_stores = set()
        for p in self.market_data:
            store = (
                p.get("supermarket", {}).get("name")
                if isinstance(p.get("supermarket"), dict)
                else p.get("store")
            )
            if store:
                unique_stores.add(store)

        store_scenarios = []

        for store in unique_stores:
            store_total = 0.0
            found_items = []
            missing_items = []

            for cart_item in self.user_cart:
                best_in_store = self._find_best_in_specific_store(cart_item, store)
                if best_in_store:
                    store_total += best_in_store["price"]
                    found_items.append(best_in_store)
                else:
                    missing_items.append(cart_item)

            store_scenarios.append(
                {
                    "store": store,
                    "total": round(store_total, 2),
                    "count_found": len(found_items),
                    "found_items": found_items,
                    "missing_items": missing_items,
                    "coverage_pct": (len(found_items) / len(self.user_cart)) * 100,
                }
            )

        # Sort by most items found first, then by price
        store_scenarios.sort(key=lambda x: (-x["count_found"], x["total"]))
        return store_scenarios[0] if store_scenarios else None

    def _find_best_in_specific_store(
        self, item: Dict, store_name: str
    ) -> Optional[Dict]:
        """Finds the best price for an item within a specific supermarket."""
        best_price = float("inf")
        best_match = None

        for p in self.market_data:
            p_store = (
                p.get("supermarket", {}).get("name")
                if isinstance(p.get("supermarket"), dict)
                else p.get("store")
            )
            if p_store != store_name:
                continue

            if self._get_match_score(item["name"], p.get("name", "")) >= 2:
                p_price = float(p.get("price_eur") or p.get("price", 0))
                if p_price < best_price:
                    best_price = p_price
                    best_match = {
                        "name": p.get("name"),
                        "price": p_price,
                        "store": store_name,
                        "is_better": True,
                    }
        return best_match

    def get_limited_stores_plan(self, limit=2) -> Dict:
        """Finds the best combination of N stores to cover the list."""
        unique_stores = set()
        for p in self.market_data:
            # Handling different data structures for store names
            store = (
                p.get("supermarket", {}).get("name")
                if isinstance(p.get("supermarket"), dict)
                else p.get("store")
            )
            if store:
                unique_stores.add(store)

        if len(unique_stores) <= limit:
            return self.get_smart_split_plan()

        best_combination_plan = None
        min_grand_total = float("inf")

        for combo in itertools.combinations(unique_stores, limit):
            current_total = 0.0
            combo_stores_data = {store: [] for store in combo}
            missing = []

            for cart_item in self.user_cart:
                best_price_in_combo = float("inf")
                best_store_in_combo = None
                best_item_data = None

                for store in combo:
                    match = self._find_best_in_specific_store(cart_item, store)
                    if match and match["price"] < best_price_in_combo:
                        best_price_in_combo = match["price"]
                        best_store_in_combo = store
                        best_item_data = match

                if best_store_in_combo:
                    current_total += best_price_in_combo
                    combo_stores_data[best_store_in_combo].append(best_item_data)
                else:
                    missing.append(cart_item)

            # Picking logic: 1. Coverage, 2. Price
            if not best_combination_plan or len(missing) < len(
                best_combination_plan["missing"]
            ):
                best_combination_plan = {
                    "stores": combo_stores_data,
                    "total_optimized": round(current_total, 2),
                    "missing": missing,
                }
                min_grand_total = current_total
            elif (
                len(missing) == len(best_combination_plan["missing"])
                and current_total < min_grand_total
            ):
                best_combination_plan = {
                    "stores": combo_stores_data,
                    "total_optimized": round(current_total, 2),
                    "missing": missing,
                }
                min_grand_total = current_total

        return best_combination_plan
