from fastapi import FastAPI
import strawberry
from strawberry.fastapi import GraphQLRouter
from icmplib import ping, traceroute, multiping
from icmplib.exceptions import (
    NameLookupError,
    SocketPermissionError,
    SocketAddressError,
    ICMPSocketError,
)

app = FastAPI(title="Monitor de Red - GraphQL + ICMP")


# =========================
# 📤 OUTPUT TYPES
# =========================

@strawberry.type
class ResultadoPing:
    direccion: str
    activo: bool
    latencia_min_ms: float
    latencia_promedio_ms: float
    latencia_max_ms: float
    perdida_porcentaje: float
    paquetes_enviados: int
    paquetes_recibidos: int
    mensaje: str


@strawberry.type
class Salto:
    numero_salto: int
    direccion_ip: str
    latencia_ms: float
    respondio: bool


@strawberry.type
class ResultadoTraceroute:
    destino: str
    total_saltos: int
    ruta: list[Salto]
    mensaje: str


@strawberry.type
class ResultadoHost:
    direccion: str
    activo: bool
    latencia_promedio_ms: float
    perdida_porcentaje: float
    mensaje: str


@strawberry.type
class ResultadoMultiping:
    total_hosts: int
    hosts_activos: int
    hosts_inactivos: int
    resultados: list[ResultadoHost]
    mensaje: str


# =========================
# 🔍 QUERIES GRAPHQL
# =========================

@strawberry.type
class Query:

    # 🌐 PING
    @strawberry.field
    def verificar_host(self, direccion: str, paquetes: int = 4, intervalo: float = 0.2) -> ResultadoPing:
        """Hace ping a un host y devuelve estadísticas de latencia."""
        try:
            res = ping(
                direccion,
                count=paquetes,
                interval=intervalo,
                timeout=2,
                privileged=True
            )
            return ResultadoPing(
                direccion=res.address,
                activo=res.is_alive,
                latencia_min_ms=res.min_rtt,
                latencia_promedio_ms=res.avg_rtt,
                latencia_max_ms=res.max_rtt,
                perdida_porcentaje=res.packet_loss * 100,
                paquetes_enviados=res.packets_sent,
                paquetes_recibidos=res.packets_received,
                mensaje="Ping exitoso" if res.is_alive else "Host no responde",
            )
        except NameLookupError:
            return ResultadoPing(
                direccion=direccion, activo=False, latencia_min_ms=0,
                latencia_promedio_ms=0, latencia_max_ms=0,
                perdida_porcentaje=100, paquetes_enviados=paquetes,
                paquetes_recibidos=0,
                mensaje=f"Error: No se pudo resolver el nombre '{direccion}'.",
            )
        except SocketPermissionError:
            return ResultadoPing(
                direccion=direccion, activo=False, latencia_min_ms=0,
                latencia_promedio_ms=0, latencia_max_ms=0,
                perdida_porcentaje=100, paquetes_enviados=paquetes,
                paquetes_recibidos=0,
                mensaje="Error: Permisos insuficientes. Ejecuta con sudo.",
            )
        except SocketAddressError:
            return ResultadoPing(
                direccion=direccion, activo=False, latencia_min_ms=0,
                latencia_promedio_ms=0, latencia_max_ms=0,
                perdida_porcentaje=100, paquetes_enviados=paquetes,
                paquetes_recibidos=0,
                mensaje="Error: No se pudo asignar la direccion de origen al socket.",
            )
        except ICMPSocketError as e:
            return ResultadoPing(
                direccion=direccion, activo=False, latencia_min_ms=0,
                latencia_promedio_ms=0, latencia_max_ms=0,
                perdida_porcentaje=100, paquetes_enviados=paquetes,
                paquetes_recibidos=0,
                mensaje=f"Error de socket ICMP: {str(e)}",
            )

    # 🛣️ TRACEROUTE
    @strawberry.field
    def trazar_ruta(self, host: str, max_saltos: int = 30, tiempo_espera: int = 2) -> ResultadoTraceroute:
        """Traza la ruta de red hasta el destino."""
        try:
            saltos = traceroute(
                host,
                max_hops=max_saltos,
                timeout=tiempo_espera
            )
            ruta = [
                Salto(
                    numero_salto=s.distance,
                    direccion_ip=s.address,
                    latencia_ms=s.avg_rtt,
                    respondio=s.is_alive,
                )
                for s in saltos
            ]
            return ResultadoTraceroute(
                destino=host,
                total_saltos=len(ruta),
                ruta=ruta,
                mensaje=f"Ruta trazada con {len(ruta)} saltos",
            )
        except NameLookupError:
            return ResultadoTraceroute(
                destino=host, total_saltos=0, ruta=[],
                mensaje=f"Error: No se pudo resolver el nombre '{host}'.",
            )
        except SocketPermissionError:
            return ResultadoTraceroute(
                destino=host, total_saltos=0, ruta=[],
                mensaje="Error: Permisos insuficientes. Ejecuta con sudo.",
            )
        except SocketAddressError:
            return ResultadoTraceroute(
                destino=host, total_saltos=0, ruta=[],
                mensaje="Error: No se pudo asignar la direccion de origen al socket.",
            )
        except ICMPSocketError as e:
            return ResultadoTraceroute(
                destino=host, total_saltos=0, ruta=[],
                mensaje=f"Error de socket ICMP: {str(e)}",
            )

    # 📡 MULTIPING
    @strawberry.field
    def escanear_hosts(self, hosts: list[str], paquetes: int = 3, intervalo: float = 0.2) -> ResultadoMultiping:
        """Hace ping a multiples hosts y devuelve el estado de cada uno."""
        resultados = []
        try:
            resultados_raw = multiping(
                hosts,
                count=paquetes,
                interval=intervalo,
                timeout=2,
                privileged=True,
            )
            resultados = [
                ResultadoHost(
                    direccion=r.address,
                    activo=r.is_alive,
                    latencia_promedio_ms=r.avg_rtt,
                    perdida_porcentaje=r.packet_loss * 100,
                    mensaje="OK" if r.is_alive else "Sin respuesta",
                )
                for r in resultados_raw
            ]
        except Exception:
            for h in hosts:
                try:
                    r = ping(h, count=paquetes, interval=intervalo, timeout=2, privileged=True)
                    resultados.append(ResultadoHost(
                        direccion=h, activo=r.is_alive,
                        latencia_promedio_ms=r.avg_rtt,
                        perdida_porcentaje=r.packet_loss * 100,
                        mensaje="OK" if r.is_alive else "Sin respuesta",
                    ))
                except NameLookupError:
                    resultados.append(ResultadoHost(
                        direccion=h, activo=False,
                        latencia_promedio_ms=0, perdida_porcentaje=100,
                        mensaje=f"Error: No se pudo resolver '{h}'",
                    ))
                except SocketPermissionError:
                    resultados.append(ResultadoHost(
                        direccion=h, activo=False,
                        latencia_promedio_ms=0, perdida_porcentaje=100,
                        mensaje="Error: Permisos insuficientes. Ejecuta con sudo.",
                    ))
                except SocketAddressError:
                    resultados.append(ResultadoHost(
                        direccion=h, activo=False,
                        latencia_promedio_ms=0, perdida_porcentaje=100,
                        mensaje="Error: No se pudo asignar direccion de origen al socket.",
                    ))
                except ICMPSocketError as e:
                    resultados.append(ResultadoHost(
                        direccion=h, activo=False,
                        latencia_promedio_ms=0, perdida_porcentaje=100,
                        mensaje=f"Error de socket ICMP: {str(e)}",
                    ))

        activos = sum(1 for r in resultados if r.activo)
        return ResultadoMultiping(
            total_hosts=len(hosts),
            hosts_activos=activos,
            hosts_inactivos=len(hosts) - activos,
            resultados=resultados,
            mensaje=f"{activos} de {len(hosts)} hosts activos",
        )


# =========================
# 📡 CONFIGURACION GRAPHQL
# =========================
schema = strawberry.Schema(query=Query)
graphql_app = GraphQLRouter(schema)
app.include_router(graphql_app, prefix="/red-icmp")
