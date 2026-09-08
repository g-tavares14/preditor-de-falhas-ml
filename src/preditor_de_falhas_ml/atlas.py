"""Acesso ao RIPE Atlas para medições pontuais de ping."""

from math import isfinite
from types import TracebackType
from typing import Any, Self

import requests

_API_URL = "https://atlas.ripe.net/api/v2/"
_TARGET = "8.8.8.8"


class AtlasClient:
    """Compartilha uma sessão HTTP autenticada entre operações do Atlas.

    Use como context manager ou chame ``close()`` após o uso. As operações
    são síncronas; criar uma medição não aguarda sua execução nas probes.
    """

    def __init__(self, api_key: str, *, timeout: float = 30.0) -> None:
        if (
            not isinstance(api_key, str)
            or not api_key
            or any(character.isspace() for character in api_key)
            or not api_key.isascii()
            or not api_key.isprintable()
        ):
            raise ValueError(
                "Chave de API inválida (valor omitido). Informe uma chave do RIPE "
                "Atlas sem espaços, com permissões de créditos e criação de medições."
            )
        if (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or not isfinite(timeout)
            or timeout <= 0
        ):
            raise ValueError(
                f"timeout inválido: {timeout!r}. Informe segundos positivos e finitos."
            )

        def authenticate(request: requests.PreparedRequest) -> requests.PreparedRequest:
            request.headers["Authorization"] = f"Key {api_key}"
            return request

        self._timeout = timeout
        self._session = requests.Session()
        # Auth explícita impede que credenciais de .netrc substituam a chave.
        self._session.auth = authenticate
        self._session.headers.update({"Accept": "application/json"})
        self._closed = False

    def get_credits(self) -> int:
        """Retorna o saldo atual; exige permissão de leitura de créditos."""
        data = self._request("GET", "credits/")
        if not isinstance(data, dict) or type(data.get("current_balance")) is not int:
            raise ValueError(
                "Resposta de créditos inválida: current_balance ausente ou não inteiro. "
                "Confira o contrato de GET /credits/ na documentação do RIPE Atlas."
            )
        return data["current_balance"]

    def create_sample(
        self,
        *,
        country_code: str,
        probe_count: int = 1,
        packets: int = 3,
    ) -> int:
        """Cria um ping IPv4 pontual para 8.8.8.8 e retorna o ID da medição.

        A criação consome créditos. O país usa código ISO de duas letras; a
        seleção e disponibilidade das probes são decididas pelo RIPE Atlas.
        """
        if (
            not isinstance(country_code, str)
            or len(country_code.strip()) != 2
            or not country_code.strip().isascii()
            or not country_code.strip().isalpha()
        ):
            raise ValueError(
                f"country_code inválido: {country_code!r}. "
                "Informe um código de país com duas letras, como 'BR'."
            )
        if type(probe_count) is not int or probe_count <= 0:
            raise ValueError(
                f"probe_count inválido: {probe_count!r}. Informe um inteiro positivo."
            )
        if type(packets) is not int or not 1 <= packets <= 16:
            raise ValueError(
                f"packets inválido: {packets!r}. Informe um inteiro entre 1 e 16."
            )
        payload = {
            "definitions": [
                {
                    "target": _TARGET,
                    "af": 4,
                    "type": "ping",
                    "description": f"Preditor de falhas ML - ping {_TARGET}",
                    "packets": packets,
                }
            ],
            "probes": [
                {
                    "type": "countries",
                    "value": country_code.strip().upper(),
                    "requested": probe_count,
                }
            ],
            "is_oneoff": True,
        }
        data = self._request("POST", "measurements/", payload=payload)
        measurement_ids = data.get("measurements") if isinstance(data, dict) else None
        if (
            not isinstance(measurement_ids, list)
            or len(measurement_ids) != 1
            or type(measurement_ids[0]) is not int
            or measurement_ids[0] <= 0
        ):
            raise ValueError(
                "Resposta de criação inválida: esperado um ID inteiro positivo em "
                "measurements. Confira sua conta no Atlas antes de reenviar: "
                "a medição pode ter sido criada."
            )
        return measurement_ids[0]

    def get_results(self, measurement_id: int) -> list[dict[str, Any]]:
        """Retorna os resultados brutos disponíveis, sem aguardar novas respostas.

        Uma lista vazia é válida. Resultados podem estar incompletos enquanto
        as probes executam a medição; campos e valores são preservados.
        """
        if type(measurement_id) is not int or measurement_id <= 0:
            raise ValueError(
                f"measurement_id inválido: {measurement_id!r}. "
                "Informe o ID inteiro positivo retornado na criação da medição."
            )
        data = self._request("GET", f"measurements/{measurement_id}/results/")
        if not isinstance(data, list) or any(
            not isinstance(result, dict) for result in data
        ):
            raise ValueError(
                "Resposta de resultados inválida: esperada uma lista de objetos JSON. "
                "Confira o contrato de resultados na documentação do RIPE Atlas."
            )
        return data

    def close(self) -> None:
        """Fecha a sessão HTTP; chamadas repetidas não têm efeito."""
        if not self._closed:
            self._session.close()
            self._closed = True

    def __enter__(self) -> Self:
        if self._closed:
            raise ValueError("Cliente fechado. Crie outro AtlasClient para continuar.")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def _request(
        self, method: str, path: str, *, payload: dict[str, Any] | None = None
    ) -> Any:
        if self._closed:
            raise ValueError("Cliente fechado. Crie outro AtlasClient para continuar.")
        operation = f"{method} /{path}"
        creation_notice = (
            " A medição pode ter sido criada; confira sua conta antes de reenviar."
            if method == "POST"
            else ""
        )
        try:
            response = self._session.request(
                method,
                f"{_API_URL}{path}",
                json=payload,
                timeout=self._timeout,
                allow_redirects=False,
            )
        except requests.RequestException as error:
            if isinstance(error, requests.Timeout):
                detail = (
                    f"timeout de {self._timeout}s. "
                    "Verifique a conexão e o tempo de espera."
                )
            elif isinstance(error, requests.ConnectionError):
                detail = (
                    "falha de conexão. Verifique a rede e a disponibilidade do Atlas."
                )
            else:
                detail = "falha ao enviar a requisição. Verifique a configuração HTTP."
            error.add_note(f"{operation}: {detail}{creation_notice}")
            raise
        if not 200 <= response.status_code < 300:
            advice = {
                400: "Revise os parâmetros, o saldo de créditos e as quotas da conta.",
                401: "Verifique a chave de API e suas permissões.",
                403: "Verifique as permissões da chave e as restrições da conta.",
                404: "Verifique o ID da medição e sua permissão de acesso.",
                429: "Aguarde o limite da API; consulte o cabeçalho Retry-After.",
            }.get(
                response.status_code,
                "Verifique a disponibilidade e a resposta do Atlas.",
            )
            raise requests.HTTPError(
                f"{operation}: HTTP {response.status_code}. {advice}{creation_notice}",
                response=response,
            )
        try:
            return response.json()
        except requests.exceptions.JSONDecodeError:
            raise ValueError(
                f"{operation}: resposta não contém JSON válido. "
                f"Verifique a resposta do Atlas.{creation_notice}"
            ) from None
