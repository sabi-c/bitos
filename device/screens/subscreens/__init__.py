"""Bitos subscreens package."""


class EmailComposeSubscreen:
    def receive_keyboard_input(self, text: str, cursor: int) -> bool:
        _ = (text, cursor)
        return True


class SMSComposeSubscreen:
    def receive_keyboard_input(self, text: str, cursor: int) -> bool:
        _ = (text, cursor)
        return True
