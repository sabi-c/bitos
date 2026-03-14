"""AUTH_CHALLENGE characteristic placeholder."""


class AuthChallengeCharacteristic:
    def __init__(self, auth_manager):
        self._auth_manager = auth_manager

    def read_value(self) -> dict:
        return self._auth_manager.get_challenge()
