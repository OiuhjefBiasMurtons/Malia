import asyncio

async def retry_async(fn, *, attempts=3, base_delay=0.4, exc=(Exception,)):
    """
    Reintenta await fn() hasta `attempts` veces.
    Entre intentos espera un 'backoff' exponencial: base, 2*base, 4*base, ...
    - fn: función sin argumentos que devuelve una coroutine (p.ej. lambda: whatsapp.send_message(...))
    - attempts: cuántos intentos en total (p.ej. 3)
    - base_delay: segundos de espera inicial (p.ej. 0.4 -> 0.4s, luego 0.8s, luego 1.6s)
    - exc: tupla de tipos de excepción que deben activar el retry (por defecto Exception)
    """
    last = None
    for i in range(attempts):
        try:
            return await fn()
        except exc as e:
            last = e
            if i == attempts - 1:
                raise
            await asyncio.sleep(base_delay * (2 ** i))
