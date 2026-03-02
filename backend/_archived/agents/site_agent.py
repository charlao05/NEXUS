try:
    from backend.utils import config_loader, llm_client
    from backend.utils.logging_utils import get_logger
    from backend.browser import playwright_client
    from backend.browser import actions
except ImportError:
    # Fallback se imports falha (ex: quando rodando em dev)
    from ..utils import config_loader, llm_client
    from ..utils.logging_utils import get_logger
    from ..browser import playwright_client
    from ..browser import actions

logger = get_logger(__name__)


def planejar(site: str, objetivo: str) -> dict:
    """
    Usa o LLM para gerar um plano de automação baseado na config do site.
    """
    logger.info(f"Planejando objetivo '{objetivo}' para o site '{site}'")

    config_site = config_loader.carregar_config_site(site)

    # O cliente LLM espera o argumento chamado `contexto_site`.
    plano = llm_client.gerar_plano_acao(
        site=site,
        objetivo=objetivo,
        contexto_site=config_site,
    )
    return plano


def executar_plano(site: str, plano: dict) -> None:
    """Executa um plano simples retornado pelo LLM.

    O plano esperado é um dicionário com a chave `steps` contendo uma lista de
    passos. Cada passo pode ter chaves em português ou inglês para máxima
    tolerância: `acao`/`action`, `url`, `selector`/`seletor`, `texto`/`text`,
    `secret`.
    """

    logger.info("Executando plano para site %s", site)

    p, browser, page = None, None, None
    try:
        p, browser, page = playwright_client.iniciar_navegador()

        steps = plano.get("steps", []) if isinstance(plano, dict) else []

        for idx, step in enumerate(steps, start=1):
            logger.info("Passo %d: %s", idx, step)

            # Suporta dois formatos de passo:
            # 1) formato do llm_client: {"tipo": "open_url", "parametros": {"url": "..."}}
            # 2) formato legado/mais explícito: {"acao": "abrir_url", "url": "..."}

            if isinstance(step, dict) and "tipo" in step:
                tipo = step.get("tipo")
                parametros = step.get("parametros", {}) or {}

                if tipo in ("open_url", "abrir_url"):
                    url = parametros.get("url")
                    if url:
                        actions.abrir_url(page, url)
                    else:
                        logger.warning(
                            "open_url sem 'url' nos parametros: %s", parametros
                        )
                elif tipo in ("click", "clicar"):
                    selector = parametros.get("selector") or parametros.get("seletor")
                    if selector:
                        actions.clicar(page, selector)
                    else:
                        logger.warning(
                            "click sem 'selector' nos parametros: %s", parametros
                        )
                elif tipo in ("type", "digitar"):
                    selector = parametros.get("selector") or parametros.get("seletor")
                    text = parametros.get("text") or parametros.get("texto")
                    secret = bool(parametros.get("secret", False))
                    if selector and text is not None:
                        actions.digitar(page, selector, text, secret=secret)
                    else:
                        logger.warning("type sem selector/text: %s", parametros)
                elif tipo in ("wait_selector", "esperar_selector"):
                    selector = parametros.get("selector") or parametros.get("seletor")
                    timeout = parametros.get("timeout_ms") or parametros.get("timeout")
                    if selector:
                        if timeout is None:
                            actions.esperar_selector(page, selector)
                        else:
                            actions.esperar_selector(
                                page, selector, timeout_ms=int(timeout)
                            )
                    else:
                        logger.warning("wait_selector sem selector: %s", parametros)
                elif tipo in ("wait_seconds", "aguardar_segundos"):
                    seconds = parametros.get("seconds") or parametros.get("segundos", 2)
                    try:
                        actions.wait_seconds(page, int(seconds))
                    except ValueError:
                        logger.warning("wait_seconds com valor inválido: %s", seconds)
                elif tipo in ("press_key", "pressionar_tecla"):
                    key = parametros.get("key") or parametros.get("tecla")
                    if key:
                        actions.press_key(page, key)
                    else:
                        logger.warning("press_key sem 'key': %s", parametros)
                else:
                    logger.warning("Tipo de passo não suportado: %s", tipo)
            else:
                # Formato legado/alternativo
                action = None
                url = None
                selector = None
                texto = None
                secret = False

                if isinstance(step, dict):
                    action = step.get("acao") or step.get("action")
                    url = step.get("url")
                    selector = step.get("selector") or step.get("seletor")
                    texto = step.get("texto") or step.get("text")
                    secret = bool(step.get("secret", False))

                if action in ("abrir_url", "open_url") and url:
                    actions.abrir_url(page, url)
                elif action in ("clicar", "click") and selector:
                    actions.clicar(page, selector)
                elif action in ("digitar", "type") and selector and texto is not None:
                    actions.digitar(page, selector, texto, secret=secret)
                elif action in ("esperar_selector", "wait_for_selector") and selector:
                    timeout = step.get("timeout_ms") or step.get("timeout")
                    if timeout is None:
                        actions.esperar_selector(page, selector)
                    else:
                        actions.esperar_selector(
                            page, selector, timeout_ms=int(timeout)
                        )
                else:
                    logger.warning(
                        "Ação não reconhecida ou parâmetros faltando: %s", step
                    )

    except Exception as exc:  # noqa: BLE001
        logger.exception("Erro ao executar o plano: %s", exc)
        raise
    finally:
        try:
            playwright_client.fechar_navegador(p, browser)
        except Exception:
            logger.exception("Erro ao fechar o navegador")
