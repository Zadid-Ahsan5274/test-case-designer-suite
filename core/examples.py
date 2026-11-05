"""Ready-made demo projects."""
from __future__ import annotations

from .decision_table import combo_key, full_combos
from .models import Condition, FieldSpec
from .project import Project


def age_example() -> Project:
    return Project(name="Age field", prefix="TC-AGE",
                   fields=[FieldSpec("Age", "int", 18, 60)])


def registration_example() -> Project:
    return Project(name="Registration form", prefix="TC-REG", fields=[
        FieldSpec("Age", "int", 18, 60),
        FieldSpec("Username", "string", 5, 15),
        FieldSpec("Account tier", "enum", allowed=["Silver", "Gold", "Platinum"]),
        FieldSpec("Discount %", "decimal", "0", "100", "0.5", required=False),
        FieldSpec("Terms accepted", "bool"),
        FieldSpec("Start date", "date", "2024-01-01", "2024-12-31"),
    ])


LOGIN_CONDITIONS = [
    Condition("Username valid"), Condition("Password valid"),
    Condition("Account locked"), Condition("Captcha solved"),
]
LOGIN_ACTIONS = ["Login success", "Invalid credentials error", "Account locked message",
                 "Captcha error"]


def login_example() -> Project:
    """Login rules with priority: locked > captcha > credentials."""
    conds = [Condition(c.name, list(c.values)) for c in LOGIN_CONDITIONS]
    amap: dict[str, list[str]] = {}
    for combo in full_combos(conds):
        if combo["Account locked"] == "Y":
            act = "Account locked message"
        elif combo["Captcha solved"] == "N":
            act = "Captcha error"
        elif combo["Username valid"] == "Y" and combo["Password valid"] == "Y":
            act = "Login success"
        else:
            act = "Invalid credentials error"
        amap[combo_key(conds, combo)] = [act]
    return Project(name="Login", prefix="TC-LOGIN", conditions=conds,
                   actions=list(LOGIN_ACTIONS), action_map=amap)


def shipping_example() -> Project:
    """Multi-value conditions - shows why pairwise helps."""
    conds = [
        Condition("User type", ["Guest", "Member", "Admin"]),
        Condition("Payment", ["Card", "Wallet", "Cash on delivery"]),
        Condition("Destination", ["Domestic", "International"]),
        Condition("Coupon", ["None", "Valid", "Expired"]),
    ]
    acts = ["Order placed", "Order placed with discount", "Payment method rejected",
            "Coupon rejected"]
    amap = {}
    for combo in full_combos(conds):
        if combo["Payment"] == "Cash on delivery" and combo["Destination"] == "International":
            a = "Payment method rejected"
        elif combo["Coupon"] == "Expired":
            a = "Coupon rejected"
        elif combo["Coupon"] == "Valid" and combo["User type"] != "Guest":
            a = "Order placed with discount"
        else:
            a = "Order placed"
        amap[combo_key(conds, combo)] = [a]
    return Project(name="Checkout", prefix="TC-CHK", conditions=conds, actions=acts,
                   action_map=amap)


def default_project() -> Project:
    """What a first-time visitor sees: Age field + Login decision table."""
    a, l = age_example(), login_example()
    return Project(name="Demo project", prefix="TC", fields=a.fields, conditions=l.conditions,
                   actions=l.actions, action_map=l.action_map)


FIELD_EXAMPLES = {"Age 18-60 (single field)": age_example,
                  "Registration form (6 fields)": registration_example}
DECISION_EXAMPLES = {"Login (4 Y/N conditions)": login_example,
                     "Checkout (multi-value, pairwise demo)": shipping_example}
