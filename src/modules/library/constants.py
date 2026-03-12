CHARGES_TOPIC_NAME: list[str] = ["🌅 Зарядка пробуждения", "🌊 Биоэнергетика", "1"]


def is_charges_topic(*categories: str | None) -> bool:
    normalized_names = {name.strip().lower() for name in CHARGES_TOPIC_NAME}
    for category in categories:
        if not category:
            continue
        if category.strip().lower() in normalized_names:
            return True
    return False
