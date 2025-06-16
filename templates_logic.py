import json
import random

with open("yo_bic_templates_200.json", "r", encoding="utf-8") as f:
    TEMPLATES = json.load(f)

def get_reply_from_templates(message: str, tone: str = "default") -> str:
    """
    Возвращает шаблонный ответ на основе ключевых слов.
    tone — "default", "aggressive", "soft", и т.д.
    """
    message = message.lower()
    for keyword, replies in TEMPLATES.items():
        if keyword in message:
            if isinstance(replies, list):
                return random.choice(replies)
            return replies
    return "Ты чё там пишешь, я не понял. Попробуй внятнее, а то как попугай с инсультом."
