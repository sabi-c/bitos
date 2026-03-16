"""AUTH_RESPONSE characteristic placeholder."""


class AuthResponseCharacteristic:
    def __init__(self, auth_manager):
        self._auth_manager = auth_manager

    def write_value(
        self,
        client_addr: str,
        nonce: str,
        response_hex: str,
        pairing_session: str | None = None,
        pairing_token: str | None = None,
    ) -> str:
        return self._auth_manager.verify_response(
            client_addr=client_addr,
            nonce=nonce,
            response_hex=response_hex,
            pairing_session_id=pairing_session,
            pairing_token=pairing_token,
        )
