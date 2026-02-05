# Кеширане на съобщения на ботa за всеки потребител
user_messages = {}

def add_message(user_id: int, message_id: int):
    if user_id not in user_messages:
        user_messages[user_id] = []
    user_messages[user_id].append(message_id)
    # пазим максимум 50 съобщения
    if len(user_messages[user_id]) > 50:
        user_messages[user_id] = user_messages[user_id][-50:]

def get_messages(user_id: int):
    return user_messages.get(user_id, [])

def clear_messages(user_id: int):
    if user_id in user_messages:
        del user_messages[user_id]
