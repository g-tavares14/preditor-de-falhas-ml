"""Gateway HTTP do RIPE Atlas: sessão, JSON e tradução para o domínio."""

from collections.abc import Callable
from math import isfinite
from time import time
from types import TracebackType
from typing import Any, Self

import requests

from preditor_de_falhas_ml.application.ports import GatewayError, GatewaySnapshot
from preditor_de_falhas_ml.domain.ids import (
    MeasurementId,
    ObservationKey,
    ProbeId,
    require_int,
)
from preditor_de_falhas_ml.domain.ping import (
    Packet,
    PacketError,
    PingSample,
    Reply,
    Timeout,
    UnusableResult,
)
from preditor_de_falhas_ml.domain.spec import (
    CountrySelection,
    MeasurementDefinition,
    MeasurementSpec,
    ResultFilters,
)

_API_URL = "https://atlas.ripe.net/api/v2/"


def parse_definition(
    data: object, measurement_id: MeasurementId
) -> MeasurementDefinition:
    """Converte o JSON de GET /measurements/{id}/ em definição de domínio."""
    if not isinstance(data, dict):
        raise ValueError(
            "Definição de medição inválida: esperado um objeto JSON. "
            "Confira o ID e o contrato de medições do Atlas."
        )
    identifier = data.get("id")
    if identifier != measurement_id.value:
        raise ValueError(
            f"id inválido: {identifier!r}. Esperado {measurement_id.value}."
        )
    kind = data.get("type")
    target = data.get("target")
    family = data.get("af")
    size = data.get("size")
    return MeasurementDefinition(
        measurement_id=measurement_id,
        type=kind if isinstance(kind, str) else "",
        target=target if isinstance(target, str) else "",
        address_family=family if type(family) is int else 0,
        size=size if type(size) is int else None,
    )


def _optional_int(value: object, field: str, *, minimum: int) -> int | None:
    if value is None:
        return None
    return require_int(value, field, minimum=minimum)


def _parse_packets(
    packets: object, context: str
) -> tuple[tuple[Packet, ...], int] | str:
    if not isinstance(packets, list):
        return (
            f"{context}: result inválido, tipo {type(packets).__name__}. "
            "Consulte os resultados brutos e forneça a lista de pacotes."
        )
    parsed: list[Packet] = []
    duplicates = 0
    for index, packet in enumerate(packets):
        field = f"{context}, result[{index}]"
        if not isinstance(packet, dict):
            return (
                f"{field} inválido: tipo {type(packet).__name__}. "
                "Forneça um objeto de resposta, timeout ou erro do Atlas."
            )
        try:
            duplicate = require_int(packet.get("dup", 0), f"{field}.dup")
        except ValueError as error:
            return str(error)
        if duplicate not in (0, 1):
            return f"{field}.dup inválido: {duplicate!r}. Use 0 ou 1 conforme o Atlas."
        if "rtt" in packet and "x" not in packet and "error" not in packet:
            rtt = packet["rtt"]
            if type(rtt) not in (int, float):
                return (
                    f"{field}.rtt inválido: {rtt!r}. Forneça milissegundos numéricos."
                )
            try:
                Reply(rtt)
            except ValueError as error:
                return (
                    str(error)
                    .replace("rtt inválido", f"{field}.rtt inválido")
                    .replace("rtt fora", f"{field}.rtt fora")
                )
            if duplicate:
                duplicates += 1
                continue
            parsed.append(Reply(float(rtt)))
        elif (
            not duplicate
            and "rtt" not in packet
            and (
                (packet.get("x") == "*" and "error" not in packet)
                or (isinstance(packet.get("error"), str) and "x" not in packet)
            )
        ):
            parsed.append(
                Timeout()
                if packet.get("x") == "*"
                else PacketError(str(packet["error"]))
            )
        else:
            return (
                f"{field} inválido: resposta, timeout ou erro ausente ou conflitante. "
                "Consulte results e confira o formato dos pacotes no Atlas."
            )
    return tuple(parsed), duplicates


def parse_result(
    raw: object,
    *,
    index: int,
    measurement_id: MeasurementId,
    definition: MeasurementDefinition | None,
) -> PingSample | UnusableResult:
    """Traduz um item de GET /results/ em amostra ou item inutilizável."""
    if not isinstance(raw, dict):
        return UnusableResult(
            index,
            f"Resultado inválido: tipo {type(raw).__name__}. "
            "Forneça um objeto de ping retornado pela consulta de resultados.",
        )
    try:
        key = ObservationKey(
            measurement_id=MeasurementId(
                require_int(raw.get("msm_id"), "msm_id", minimum=1)
            ),
            probe_id=ProbeId(require_int(raw.get("prb_id"), "prb_id", minimum=1)),
            timestamp=require_int(raw.get("timestamp"), "timestamp"),
        )
    except ValueError as error:
        return UnusableResult(index, str(error))

    def unusable(reason: str) -> UnusableResult:
        destination = (
            raw.get("dst_addr") if isinstance(raw.get("dst_addr"), str) else None
        )
        family = raw.get("af") if type(raw.get("af")) is int else None
        if destination in (None, "") and definition is not None:
            destination = definition.target
        if family is None and definition is not None:
            family = definition.address_family
        return UnusableResult(
            index,
            reason,
            key=key,
            destination=destination or None,
            address_family=family,
        )

    if raw.get("msm_id") != measurement_id.value:
        return unusable(
            f"msm_id inválido: {raw.get('msm_id')!r}. Esperado {measurement_id.value} para esta consulta."
        )
    if raw.get("type") != "ping":
        return unusable(
            f"type inválido: {raw.get('type')!r}. Selecione uma medição de ping para calcular os atributos."
        )
    if raw.get("proto", "ICMP") != "ICMP":
        return unusable(f"proto inválido: {raw.get('proto')!r}. Use ping ICMP.")

    raw_destination = raw.get("dst_addr")
    if raw_destination in (None, ""):
        destination = definition.target if definition is not None else None
        source = "definition"
    else:
        destination = raw_destination if isinstance(raw_destination, str) else None
        source = "result"
    family = raw.get("af")
    if type(family) is not int:
        family = definition.address_family if definition is not None else None
    if not isinstance(destination, str) or not destination or family not in (4, 6):
        return unusable(
            f"Medição {measurement_id.value}: destino/af inválidos: {destination!r}/{family!r}. "
            "Informe um destino e a família 4 ou 6; se o endereço estiver ausente, forneça a definição."
        )

    context = f"Medição {measurement_id.value}, probe {key.probe_id.value}, timestamp {key.timestamp}"
    parsed = _parse_packets(raw.get("result"), context)
    if isinstance(parsed, str):
        return unusable(parsed)
    packets, duplicates = parsed

    size = raw.get("size", definition.size if definition is not None else None)
    lts = raw.get("lts")
    ttl = raw.get("ttl")
    firmware = raw.get("fw")
    version = raw.get("mver")
    try:
        size_value = _optional_int(size, "size", minimum=0)
        lts_value = _optional_int(lts, "lts", minimum=-1)
        if lts_value == -1:
            lts_value = None
        ttl_value = _optional_int(ttl, "reply_ttl", minimum=0)
        if ttl_value is not None and ttl_value > 255:
            return unusable(f"ttl inválido: {ttl_value!r}. Informe TTL entre 0 e 255.")
        firmware_value = _optional_int(firmware, "fw", minimum=1)
    except ValueError as error:
        return unusable(str(error))
    if version is not None and not isinstance(version, str):
        return unusable(f"mver inválido: {version!r}. Preserve a versão como texto.")

    replies = sum(isinstance(packet, Reply) for packet in packets)
    return PingSample(
        key=key,
        destination=destination,
        address_family=family,
        destination_source=source,
        sent=len(packets),
        received=replies,
        duplicates=duplicates,
        packets=packets,
        size=size_value,
        lts=lts_value,
        reply_ttl=ttl_value,
        firmware=firmware_value,
        measurement_version=version,
    )


class AtlasGateway:
    """Sessão HTTP do Atlas. Sem chave, só consultas públicas."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        timeout: float = 30.0,
        clock: Callable[[], float] | None = None,
    ) -> None:
        if api_key is not None and (
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

        self._api_key = api_key
        self._timeout = timeout
        self._clock = clock or time
        self._session = requests.Session()
        self._session.headers.update({"Accept": "application/json"})
        # Auth explícita (ou identidade) impede que .netrc substitua a decisão.
        if api_key is None:

            def anonymous(
                request: requests.PreparedRequest,
            ) -> requests.PreparedRequest:
                return request

            self._session.auth = anonymous
        else:

            def authenticate(
                request: requests.PreparedRequest,
            ) -> requests.PreparedRequest:
                request.headers["Authorization"] = f"Key {api_key}"
                return request

            self._session.auth = authenticate
        self._closed = False

    def _require_key(self, *, creating: bool) -> None:
        if self._api_key is None:
            raise GatewayError(
                "Chave de API ausente. Defina RIPE_ATLAS_API_KEY para criar "
                "medições ou consultar créditos.",
                creating=creating,
            )

    def get_credits(self) -> int:
        self._require_key(creating=False)
        data = self._request("GET", "credits/")
        if not isinstance(data, dict) or type(data.get("current_balance")) is not int:
            raise ValueError(
                "Resposta de créditos inválida: current_balance ausente ou não inteiro. "
                "Confira o contrato de GET /credits/ na documentação do RIPE Atlas."
            )
        return data["current_balance"]

    def create(self, spec: MeasurementSpec) -> MeasurementId:
        self._require_key(creating=True)
        if isinstance(spec.selection, CountrySelection):
            selection = {
                "type": "countries",
                "value": spec.selection.country_code,
                "requested": spec.selection.probe_count,
            }
        else:
            selection = {
                "type": "probes",
                "value": ",".join(str(probe) for probe in spec.selection.probe_ids),
                "requested": len(spec.selection.probe_ids),
            }
        payload: dict[str, Any] = {
            "definitions": [
                {
                    "target": spec.target,
                    "af": spec.address_family,
                    "type": "ping",
                    "description": f"Preditor de falhas ML - ping {spec.target}",
                    "packets": spec.packets,
                    "size": spec.size,
                }
            ],
            "probes": [selection],
            "is_oneoff": spec.is_oneoff,
        }
        if not spec.is_oneoff:
            payload["interval"] = spec.interval
            payload["stop_time"] = int(self._clock()) + spec.duration
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
        return MeasurementId(measurement_ids[0])

    def load_snapshot(
        self, measurement_id: MeasurementId, filters: ResultFilters
    ) -> GatewaySnapshot:
        try:
            definition = parse_definition(
                self._request("GET", f"measurements/{measurement_id.value}/"),
                measurement_id,
            )
        except ValueError:
            definition = None
        params: dict[str, int] = {}
        if filters.probe_id is not None:
            params["probe"] = filters.probe_id.value
        if filters.start is not None:
            params["start"] = filters.start
        if filters.stop is not None:
            params["stop"] = filters.stop
        data = self._request(
            "GET",
            f"measurements/{measurement_id.value}/results/",
            params=params or None,
        )
        if not isinstance(data, list):
            raise ValueError(
                "Resposta de resultados inválida: esperada uma lista JSON. "
                "Confira o contrato de resultados na documentação do RIPE Atlas."
            )
        items = tuple(
            parse_result(
                raw, index=index, measurement_id=measurement_id, definition=definition
            )
            for index, raw in enumerate(data)
        )
        return GatewaySnapshot(definition, items, tuple(data))

    def close(self) -> None:
        if not self._closed:
            self._session.close()
            self._closed = True

    def __enter__(self) -> Self:
        if self._closed:
            raise ValueError("Cliente fechado. Crie outro AtlasGateway para continuar.")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def _request(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        params: dict[str, int] | None = None,
    ) -> Any:
        if self._closed:
            raise ValueError("Cliente fechado. Crie outro AtlasGateway para continuar.")
        operation = f"{method} /{path}"
        creating = method == "POST"
        creation_notice = (
            " A medição pode ter sido criada; confira sua conta antes de reenviar."
            if creating
            else ""
        )
        try:
            response = self._session.request(
                method,
                f"{_API_URL}{path}",
                json=payload,
                params=params,
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
            raise GatewayError(
                f"{operation}: {detail}{creation_notice}", creating=creating
            ) from error
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
            raise GatewayError(
                f"{operation}: HTTP {response.status_code}. {advice}{creation_notice}",
                creating=creating,
            ) from None
        try:
            return response.json()
        except requests.exceptions.JSONDecodeError:
            raise ValueError(
                f"{operation}: resposta não contém JSON válido. "
                f"Verifique a resposta do Atlas.{creation_notice}"
            ) from None
