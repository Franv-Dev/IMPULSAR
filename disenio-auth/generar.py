"""Arma los artboards de auth desde una sola plantilla.

Los tres tratamientos de fondo comparten EXACTAMENTE el mismo formulario: si se
escribiera tres veces a mano, al primer retoque quedarían distintos y la
comparación dejaría de ser sobre el fondo. Acá el formulario está una sola vez
y lo que cambia es el bloque de atmósfera.

Se corre a mano cuando se toca algo:  python generar.py
"""

from pathlib import Path

AQUI = Path(__file__).parent

# Los siete pares de rubro, tal como están en static/css/styles.css. Las
# baldosas de la vidriera son eso: los colores reales de la plataforma.
RUBROS = [
    ("#FDECE5", "#9A5230"),  # alimentos
    ("#E5F5EC", "#1C7B53"),  # hogar
    ("#EEEFFE", "#635EA3"),  # artesanias
    ("#FBEBF2", "#954D71"),  # indumentaria
    ("#E5F2FD", "#1D6FA0"),  # tecnologia
    ("#F4F0E1", "#7C6700"),  # servicios
    ("#EEF1F7", "#5F6B7C"),  # otros
]

CABEZA = """<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <script src="./support.js"></script>
</head>
<body>
<x-dc>
<helmet>
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Poppins:wght@500;600;700&family=Inter:wght@400;500;600&display=swap">
  <style>
    body {{ margin: 0; font-family: "Inter", system-ui, -apple-system, "Segoe UI", sans-serif; color: #1B2430; background: {fondo_body}; -webkit-font-smoothing: antialiased; }}
    a {{ color: #3E2F94; text-decoration: none; }}
    a:hover {{ color: #33267C; }}
    h1, h2, h3 {{ font-family: "Poppins", system-ui, sans-serif; margin: 0; text-wrap: pretty; }}
    button {{ font-family: inherit; }}
    .u-btn-primario:hover {{ background: #483BA1; color: #FFFFFF; }}
    .u-campo:focus-within {{ border-color: #3E2F94; background: #FFFFFF; box-shadow: 0 0 0 3px #ECEAF7; }}
    .u-ficha:hover {{ border-color: #C2BAE6; background: #FFFFFF; }}
    .u-link-suave:hover {{ text-decoration: underline; }}
    /* Las baldosas de la vidriera: tarjetas de emprendimiento insinuadas. */
    .v-baldosa {{ display: flex; flex-direction: column; gap: 10px; padding: 14px; border-radius: 18px; background: {baldosa_fondo}; box-shadow: {baldosa_sombra}; }}
    .v-foto {{ border-radius: 13px; }}
    .v-linea {{ height: 9px; border-radius: 999px; background: {linea}; }}
    .v-punto {{ width: 10px; height: 10px; border-radius: 999px; flex-shrink: 0; }}
  </style>
</helmet>
"""

# --- El formulario. Uno solo, para los tres fondos. ---------------------------

FICHA_ROL = """
      <div style="margin-bottom: 20px">
        <span style="display: block; margin-bottom: 10px; font-size: 12.5px; font-weight: 600">¿Para qué vas a usar IMPULSAR?</span>
        <div style="display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px">

          <div style="display: flex; flex-direction: column; gap: 8px; padding: 14px 14px 15px; border: 2px solid #3E2F94; border-radius: 15px; background: #F7F6FD; cursor: pointer">
            <span style="display: flex; align-items: center; justify-content: space-between">
              <span style="display: inline-flex; align-items: center; justify-content: center; width: 34px; height: 34px; border-radius: 11px; background: #ECEAF7; color: #3E2F94">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M4.6 6.2h2.2l2 8.6h8.4l1.8-6.2H7.6"/><circle cx="10" cy="18.6" r="1.4"/><circle cx="16.4" cy="18.6" r="1.4"/></svg>
              </span>
              <span style="display: inline-flex; align-items: center; justify-content: center; width: 20px; height: 20px; border-radius: 999px; background: #3E2F94; color: #FFFFFF">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="m5.5 12.4 4.2 4.2 8.8-9.2"/></svg>
              </span>
            </span>
            <span style="font-family: 'Poppins', sans-serif; font-size: 14.5px; font-weight: 600">Comprar</span>
            <span style="font-size: 12px; line-height: 1.45; color: #5F6B7C">Busco, guardo favoritos y pido presupuestos.</span>
          </div>

          <div class="u-ficha" style="display: flex; flex-direction: column; gap: 8px; padding: 15px; border: 1px solid #E2E6EE; border-radius: 15px; background: #FFFFFF; cursor: pointer; transition: border-color .15s ease, background .15s ease">
            <span style="display: flex; align-items: center; justify-content: space-between">
              <span style="display: inline-flex; align-items: center; justify-content: center; width: 34px; height: 34px; border-radius: 11px; background: #FDECE5; color: #9A5230">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M4.4 9.6 6 5.2h12l1.6 4.4a3 3 0 0 1-5.6 1.9 3 3 0 0 1-5.6 0 3 3 0 0 1-4 .5"/><path d="M6.2 11.8v7h11.6v-7"/></svg>
              </span>
              <span style="display: inline-block; width: 20px; height: 20px; border: 1.5px solid #D5DAE5; border-radius: 999px"></span>
            </span>
            <span style="font-family: 'Poppins', sans-serif; font-size: 14.5px; font-weight: 600">Vender</span>
            <span style="font-size: 12px; line-height: 1.45; color: #5F6B7C">Publico mi emprendimiento, horarios y ferias.</span>
          </div>

        </div>
      </div>
"""

CAMPOS_REGISTRO = """
      <div style="display: flex; flex-direction: column; gap: 15px">

        <label style="display: block">
          <span style="display: block; margin-bottom: 7px; font-size: 12.5px; font-weight: 600">Usuario</span>
          <span class="u-campo" style="display: flex; align-items: center; gap: 11px; height: 48px; padding: 0 14px; border: 1px solid #E2E6EE; border-radius: 13px; background: #F7F9FC; transition: border-color .15s ease, box-shadow .15s ease, background .15s ease">
            <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="#5F6B7C" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8.4" r="3.8"/><path d="M4.8 19.6a7.2 7.2 0 0 1 14.4 0"/></svg>
            <span style="flex: 1; font-size: 15px; color: #1B2430">marina.cabral</span>
            <span style="display: inline-flex; align-items: center; gap: 5px; font-size: 12px; font-weight: 600; color: #1F7A4D">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="m5.5 12.4 4.2 4.2 8.8-9.2"/></svg>
              Disponible
            </span>
          </span>
        </label>

        <label style="display: block">
          <span style="display: block; margin-bottom: 7px; font-size: 12.5px; font-weight: 600">Email</span>
          <span class="u-campo" style="display: flex; align-items: center; gap: 11px; height: 48px; padding: 0 14px; border: 1px solid #E2E6EE; border-radius: 13px; background: #F7F9FC; transition: border-color .15s ease, box-shadow .15s ease, background .15s ease">
            <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="#5F6B7C" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="3.6" y="5.4" width="16.8" height="13.2" rx="2.4"/><path d="m4.4 7.4 7.6 5.4 7.6-5.4"/></svg>
            <span style="font-size: 15px; color: #5F6B7C">tucorreo@ejemplo.com</span>
          </span>
        </label>

        <label style="display: block">
          <span style="display: block; margin-bottom: 7px; font-size: 12.5px; font-weight: 600">Contraseña</span>
          <span class="u-campo" style="display: flex; align-items: center; gap: 11px; height: 48px; padding: 0 12px 0 14px; border: 1px solid #E2E6EE; border-radius: 13px; background: #F7F9FC; transition: border-color .15s ease, box-shadow .15s ease, background .15s ease">
            <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="#5F6B7C" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="4.8" y="10.4" width="14.4" height="9.4" rx="2.4"/><path d="M8.4 10.4V7.8a3.6 3.6 0 0 1 7.2 0v2.6"/></svg>
            <span style="flex: 1; font-size: 15px; letter-spacing: .16em; color: #1B2430">••••••••••</span>
            <button type="button" aria-label="Mostrar la contraseña" title="Mostrar la contraseña" style="display: inline-flex; align-items: center; justify-content: center; width: 34px; height: 34px; padding: 0; border: none; border-radius: 999px; background: #ECEAF7; color: #3E2F94; cursor: pointer">
              <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M2.6 12S6.4 5.8 12 5.8 21.4 12 21.4 12 17.6 18.2 12 18.2 2.6 12 2.6 12Z"/><circle cx="12" cy="12" r="2.7"/></svg>
            </button>
          </span>
          <span style="display: flex; align-items: center; gap: 14px; margin-top: 9px">
            <span style="display: inline-flex; align-items: center; gap: 6px; font-size: 12px; color: #1F7A4D">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="m5.5 12.4 4.2 4.2 8.8-9.2"/></svg>
              Al menos 8 caracteres
            </span>
            <span style="display: inline-flex; align-items: center; gap: 6px; font-size: 12px; color: #1F7A4D">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="m5.5 12.4 4.2 4.2 8.8-9.2"/></svg>
              No es una de las obvias
            </span>
          </span>
        </label>

        <button type="button" class="u-btn-primario" style="display: inline-flex; align-items: center; justify-content: center; gap: 9px; width: 100%; height: 50px; margin-top: 5px; border: none; border-radius: 14px; background: #5248AE; color: #FFFFFF; font-size: 15.5px; font-weight: 600; cursor: pointer; box-shadow: 0 12px 26px rgba(62,47,148,.26)">
          Crear cuenta
          <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h13M13 6.5 18.5 12 13 17.5"/></svg>
        </button>
      </div>
"""

CAMPOS_ENTRAR = """
      <div style="display: flex; align-items: flex-start; gap: 10px; padding: 12px 14px; margin-bottom: 20px; border-radius: 12px; background: #FEE2E2; color: #B91C1C">
        <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" style="flex-shrink: 0; margin-top: 1px"><circle cx="12" cy="12" r="8.6"/><path d="M12 8v4.6M12 15.8v.1"/></svg>
        <span style="font-size: 13.5px; line-height: 1.5">La contraseña es incorrecta. Probá de nuevo o <a href="#" class="u-link-suave" style="color: #B91C1C; font-weight: 600; text-decoration: underline">creá una cuenta</a>.</span>
      </div>

      <div style="display: flex; flex-direction: column; gap: 16px">

        <label style="display: block">
          <span style="display: block; margin-bottom: 7px; font-size: 12.5px; font-weight: 600">Usuario</span>
          <span class="u-campo" style="display: flex; align-items: center; gap: 11px; height: 48px; padding: 0 14px; border: 1px solid #E2E6EE; border-radius: 13px; background: #F7F9FC; transition: border-color .15s ease, box-shadow .15s ease, background .15s ease">
            <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="#5F6B7C" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8.4" r="3.8"/><path d="M4.8 19.6a7.2 7.2 0 0 1 14.4 0"/></svg>
            <span style="font-size: 15px; color: #1B2430">marina.cabral</span>
          </span>
        </label>

        <label style="display: block">
          <span style="display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 7px">
            <span style="font-size: 12.5px; font-weight: 600">Contraseña</span>
            <a href="#" style="font-size: 12.5px; font-weight: 600">¿La olvidaste?</a>
          </span>
          <span class="u-campo" style="display: flex; align-items: center; gap: 11px; height: 48px; padding: 0 12px 0 14px; border: 1px solid #E2E6EE; border-radius: 13px; background: #F7F9FC; transition: border-color .15s ease, box-shadow .15s ease, background .15s ease">
            <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="#5F6B7C" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="4.8" y="10.4" width="14.4" height="9.4" rx="2.4"/><path d="M8.4 10.4V7.8a3.6 3.6 0 0 1 7.2 0v2.6"/></svg>
            <span style="flex: 1; font-size: 15px; letter-spacing: .16em; color: #1B2430">••••••••</span>
            <button type="button" aria-label="Mostrar la contraseña" title="Mostrar la contraseña" style="display: inline-flex; align-items: center; justify-content: center; width: 34px; height: 34px; padding: 0; border: none; border-radius: 999px; background: #ECEAF7; color: #3E2F94; cursor: pointer">
              <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M2.6 12S6.4 5.8 12 5.8 21.4 12 21.4 12 17.6 18.2 12 18.2 2.6 12 2.6 12Z"/><circle cx="12" cy="12" r="2.7"/></svg>
            </button>
          </span>
        </label>

        <button type="button" class="u-btn-primario" style="display: inline-flex; align-items: center; justify-content: center; gap: 9px; width: 100%; height: 50px; margin-top: 5px; border: none; border-radius: 14px; background: #5248AE; color: #FFFFFF; font-size: 15.5px; font-weight: 600; cursor: pointer; box-shadow: 0 12px 26px rgba(62,47,148,.26)">
          Entrar
          <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h13M13 6.5 18.5 12 13 17.5"/></svg>
        </button>
      </div>
"""


def tarjeta(modo, titulo, bajada, solapa_activa, cuerpo, pie):
    """La tarjeta blanca del formulario, igual en los tres fondos."""
    entrar_activa = solapa_activa == "entrar"
    solapa = lambda activa: (
        'flex: 1; padding: 11px 0; border-radius: 10px; text-align: center; font-size: 14px; '
        + ('font-weight: 600; background: #FFFFFF; color: #1B2430; box-shadow: 0 4px 12px rgba(15,23,42,.08)'
           if activa else 'color: #5F6B7C')
    )
    # En el fondo nocturno la tarjeta necesita más sombra para despegar.
    sombra = ("0 44px 96px rgba(8,4,28,.52), 0 4px 12px rgba(8,4,28,.34)"
              if modo in ("nocturno", "foto")
              else "0 32px 80px rgba(23,20,71,.16), 0 2px 8px rgba(23,20,71,.05)")
    return f"""
    <div style="width: 100%; max-width: 468px; padding: 36px 40px 32px; border: 1px solid rgba(255,255,255,.9); border-radius: 26px; background: #FFFFFF; box-shadow: {sombra}">

      <h1 style="font-size: 29px; letter-spacing: -.028em; line-height: 1.15; text-align: center">{titulo}</h1>
      <p style="margin: 10px 0 24px; font-size: 14.5px; line-height: 1.55; color: #5F6B7C; text-align: center">{bajada}</p>

      <div style="display: flex; gap: 4px; padding: 4px; margin-bottom: 24px; border-radius: 13px; background: #F5F7FA">
        <a href="#" style="{solapa(entrar_activa)}">Entrar</a>
        <a href="#" style="{solapa(not entrar_activa)}">Crear cuenta</a>
      </div>
{cuerpo}
      <p style="margin: 20px 0 0; font-size: 13.5px; color: #5F6B7C; text-align: center">{pie}</p>
    </div>
"""


# --- Los tres fondos ---------------------------------------------------------
#
# Ninguno es decoración suelta: los tres salen de algo que IMPULSAR ya es.
#
#   IMPULSO  la barra inclinada del logo, agrandada y puesta en ritmo.
#   MENDOZA  las curvas de nivel de la montaña, que es dónde está esto.
#   CERCA    el plano de la ciudad con el radio en km, que es LA función que
#            distingue a la plataforma (Post.latitude/longitude + el filtro de
#            radio de app/blog/consultas.py).
#
# Todos van en SVG en línea con viewBox fijo y preserveAspectRatio="slice", así
# el mismo dibujo sirve para el artboard de 1440 y para el de 390 sin rehacerlo:
# el navegador recorta en vez de deformar.

import math

ANCHO_SVG, ALTO_SVG = 1440, 1080


def _svg(contenido, extra=""):
    return (
        f'<svg viewBox="0 0 {ANCHO_SVG} {ALTO_SVG}" preserveAspectRatio="xMidYMid slice" '
        f'aria-hidden="true" style="position: absolute; inset: 0; width: 100%; height: 100%; '
        f'display: block;{extra}">\n{contenido}\n  </svg>'
    )


def fondo_impulso():
    """La barra del logo, repetida en ritmo ascendente.

    La barra es un paralelogramo inclinado: se repite catorce veces con anchos
    y opacidades distintas, más apretadas arriba a la derecha, para que se lea
    como envión y no como un patrón de papel de regalo. Dos de ellas van en
    terracota: es el acento de la paleta y evita que sea un fondo de un color.
    """
    piezas = []
    # (x de la base, ancho, opacidad, color)
    barras = [
        (-260, 96, 0.055, "#3E2F94"), (-90, 54, 0.035, "#3E2F94"),
        (10, 130, 0.070, "#3E2F94"), (200, 40, 0.030, "#D97544"),
        (280, 88, 0.045, "#3E2F94"), (420, 150, 0.060, "#3E2F94"),
        (620, 46, 0.028, "#3E2F94"), (700, 112, 0.050, "#3E2F94"),
        (860, 62, 0.034, "#D97544"), (960, 168, 0.065, "#3E2F94"),
        (1170, 50, 0.030, "#3E2F94"), (1260, 104, 0.045, "#3E2F94"),
        (1410, 74, 0.036, "#3E2F94"), (1530, 140, 0.055, "#3E2F94"),
    ]
    # 22° de inclinación, la misma que tiene la barra del logotipo.
    corrimiento = math.tan(math.radians(22)) * (ALTO_SVG + 400)
    for x, ancho, op, color in barras:
        x0, x1 = x, x + ancho
        piezas.append(
            f'    <path d="M{x0 + corrimiento:.0f} -200 H{x1 + corrimiento:.0f} '
            f'L{x1:.0f} {ALTO_SVG + 200} H{x0:.0f} Z" fill="{color}" opacity="{op}"/>'
        )
    return _svg("\n".join(piezas))


def fondo_mendoza():
    """Curvas de nivel: la montaña, que es dónde vive esto.

    Son anillos concéntricos deformados con dos senos, dibujados con la misma
    fórmula para todos, así el conjunto se lee como un relieve y no como manchas
    sueltas. El centro está fuera del lienzo, arriba a la izquierda: una
    topografía centrada parecería una diana.
    """
    cx, cy = 210.0, 165.0
    lineas = []
    for i in range(26):
        base = 130 + i * 74
        puntos = []
        for k in range(97):
            ang = 2 * math.pi * k / 96
            r = (base
                 + 46 * math.sin(3 * ang + 0.7 + i * 0.16)
                 + 26 * math.sin(5 * ang + 2.1 - i * 0.09)
                 + 13 * math.sin(8 * ang + 0.3))
            puntos.append(f"{cx + r * math.cos(ang) * 1.28:.1f},{cy + r * math.sin(ang):.1f}")
        # Las de adentro son las cumbres: van un punto más marcadas.
        op = 0.30 - i * 0.008
        ancho = 1.6 if i % 5 == 0 else 1.05
        color = "#D97544" if i in (4, 12) else "#3E2F94"
        lineas.append(
            f'    <polygon points="{" ".join(puntos)}" fill="none" stroke="{color}" '
            f'stroke-width="{ancho}" opacity="{op:.3f}"/>'
        )
    return _svg("\n".join(lineas))


def fondo_cerca():
    """El plano de la ciudad y el radio en kilómetros.

    Es la función que separa a IMPULSAR de Mercado Libre y de Marketplace, y la
    única que ya está resuelta en SQL: la trama de calles, los anillos de radio
    y unos pocos pines en los colores de rubro. Todo en gris muy claro; los
    anillos en índigo, porque son lo que importa.
    """
    partes = []
    cx, cy = 720.0, 470.0

    # La trama de calles, con la inclinación del damero mendocino.
    calles = []
    for x in range(-360, 1900, 76):
        grueso = 2.4 if (x // 76) % 4 == 0 else 1
        calles.append(f'<path d="M{x} -300 V{ALTO_SVG + 300}" stroke="#1B2430" '
                      f'stroke-width="{grueso}" opacity="{0.055 if grueso > 1 else 0.032}"/>')
    for y in range(-300, 1500, 76):
        grueso = 2.4 if (y // 76) % 4 == 0 else 1
        calles.append(f'<path d="M-360 {y} H1900" stroke="#1B2430" '
                      f'stroke-width="{grueso}" opacity="{0.055 if grueso > 1 else 0.032}"/>')
    partes.append(f'    <g transform="rotate(-7 720 540)">\n      '
                  + "\n      ".join(calles) + "\n    </g>")

    # Los anillos de radio: 1, 2, 5 y 10 km, los mismos pasos que ofrece el
    # <select> del listado.
    for i, r in enumerate((190, 330, 480, 640)):
        partes.append(
            f'    <circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#3E2F94" '
            f'stroke-width="{1.5 if i else 2}" opacity="{0.16 - i * 0.028:.3f}" '
            f'stroke-dasharray="{"none" if i == 0 else "7 9"}"/>'
        )
    partes.append(f'    <circle cx="{cx}" cy="{cy}" r="700" fill="url(#halo)"/>')

    # Unos pocos pines, en los colores de rubro. Son seis, no cuarenta: el fondo
    # tiene que insinuar, no llenarse.
    pines = [
        (352, 214, "#9A5230"), (1108, 262, "#1C7B53"), (250, 742, "#635EA3"),
        (1180, 760, "#1D6FA0"), (612, 128, "#954D71"), (940, 880, "#7C6700"),
    ]
    for x, y, color in pines:
        partes.append(
            f'    <g opacity=".5" transform="translate({x} {y})">'
            f'<path d="M0 14C0 14 9 6.4 9 0A9 9 0 1 0-9 0c0 6.4 9 14 9 14Z" fill="{color}" '
            f'opacity=".85"/><circle cy="0" r="3.4" fill="#FFFFFF"/></g>'
        )

    defs = (
        '    <defs><radialGradient id="halo">'
        '<stop offset="42%" stop-color="#3E2F94" stop-opacity=".07"/>'
        '<stop offset="100%" stop-color="#3E2F94" stop-opacity="0"/>'
        "</radialGradient></defs>"
    )
    return _svg(defs + "\n" + "\n".join(partes))


# El velo: baja el fondo justo detrás de la tarjeta para que el formulario nunca
# compita con el dibujo. Es un halo redondo, no una sábana: así los bordes del
# lienzo conservan el dibujo entero.
def velo(tono="#F4F6FA", radio=520):
    return (f'<span style="position: absolute; inset: 0; background: radial-gradient('
            f'ellipse {radio}px {radio}px at 50% 44%, {tono} 0%, {tono} 44%, '
            f'{tono}00 76%)"></span>')


def fondo_foto(clave_imagen=None, encuadre="center", marcador=True):
    """Foto a sangre con velo semioscuro, que es el pedido de Tomás.

    `clave_imagen` es el nombre del archivo tal como queda en el canvas (por
    ejemplo "taller.jpg"). Mientras no haya foto va en None y se dibuja un
    HUECO MARCADO, no una ilustración que la imite: una ilustración con cara de
    foto es peor que un hueco, porque se aprueba una cosa y llega otra.

    El hueco igual reproduce los VALORES de la foto final -- oscuro, con una luz
    cálida arriba a la izquierda como la de un taller y viñeta en los bordes --
    para que el tratamiento se pueda juzgar aunque la imagen no esté.

    Las tres capas encima de la foto, en orden:
      1. un velo de índigo profundo, que la baja a semioscura y la tiñe con el
         color de la marca en vez de dejarla en gris;
      2. un degradado vertical que oscurece arriba y abajo, para que el logo y
         la línea del pie se lean contra cualquier foto;
      3. una viñeta, que cierra la composición sobre la tarjeta.
    """
    if clave_imagen:
        capa = (f'  <img src="{clave_imagen}" alt="" style="position: absolute; inset: 0; '
                f'width: 100%; height: 100%; object-fit: cover; object-position: {encuadre}; '
                f'display: block">')
    else:
        # La luz del hueco va SIEMPRE que no haya foto: es la que reproduce los
        # valores de la imagen final y sin ella el fondo queda plano.
        capa = """  <span style="position: absolute; inset: 0; background:
      radial-gradient(ellipse 900px 620px at 26% 18%, #6E5A3A 0%, #3A2E44 46%, #1A1330 100%)"></span>"""
        # El cartel con la medida, en cambio, es una nota para quien mira el
        # artboard de escritorio. En 390 px se parte en tres renglones y se le
        # encima al logotipo, así que ahí no va.
        if marcador:
            capa += """
  <span style="position: absolute; inset: 0; display: flex; align-items: flex-start; justify-content: flex-start; padding: 28px 32px">
    <span style="display: inline-flex; align-items: center; gap: 12px; padding: 12px 18px; border: 1px dashed rgba(255,255,255,.42); border-radius: 14px; color: rgba(255,255,255,.80); font-size: 12.5px; line-height: 1.5">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink: 0"><rect x="3" y="6" width="18" height="14" rx="2.6"/><path d="M8.4 6 10 3.4h4L15.6 6"/><circle cx="12" cy="13" r="3.6"/></svg>
      <span><b style="font-weight: 600">Acá va la foto</b><br>Emprendedor trabajando · 2400 × 1600 o más · horizontal<br>El sujeto va a un costado, nunca al centro: ahí va la tarjeta</span>
    </span>
  </span>"""

    return (
        capa
        + """
  <span style="position: absolute; inset: 0; background: rgba(26,19,48,.46)"></span>
  <span style="position: absolute; inset: 0; background: linear-gradient(180deg, rgba(20,14,44,.62) 0%, rgba(20,14,44,.14) 32%, rgba(20,14,44,.18) 68%, rgba(20,14,44,.70) 100%)"></span>
  <span style="position: absolute; inset: 0; background: radial-gradient(ellipse 900px 760px at 50% 46%, rgba(20,14,44,0) 32%, rgba(20,14,44,.34) 100%)"></span>"""
    )


FONDOS = {
    # LA FOTO. Es la que pidió Tomás; las tres de abajo quedan como respaldo.
    "foto": {
        "fondo_body": "#1A1330",
        "baldosa_fondo": "#FFFFFF",
        "baldosa_sombra": "none",
        "linea": "#E2E6EE",
        "atmosfera": fondo_foto(),
        # El logotipo tiene la palabra en gris azulado: sobre la foto oscura no
        # se leería. Se invierte a blanco con un filtro, sin pedir otro PNG.
        "logo_filtro": " filter: brightness(0) invert(1);",
        "pie_color": "rgba(255,255,255,.80)",
    },
    # A · El envión de la marca.
    "impulso": {
        "fondo_body": "#F4F6FA",
        "baldosa_fondo": "#FFFFFF",
        "baldosa_sombra": "none",
        "linea": "#E2E6EE",
        "atmosfera": (
            '  <span style="position: absolute; inset: 0; background: '
            'linear-gradient(158deg, #FFFFFF 0%, #F1F3F9 62%, #F7F2EE 100%)"></span>\n  '
            + fondo_impulso() + "\n  " + velo("#F6F7FB", 470)
        ),
        "logo_filtro": "",
        "pie_color": "#4A5666",
    },
    # B · La montaña.
    "mendoza": {
        "fondo_body": "#F5F7FA",
        "baldosa_fondo": "#FFFFFF",
        "baldosa_sombra": "none",
        "linea": "#E2E6EE",
        "atmosfera": (
            '  <span style="position: absolute; inset: 0; background: '
            'linear-gradient(150deg, #FBF8F5 0%, #F2F4FA 58%, #EDEFF7 100%)"></span>\n  '
            + fondo_mendoza() + "\n  " + velo("#F7F8FC", 440)
        ),
        "logo_filtro": "",
        "pie_color": "#4A5666",
    },
    # C · El plano y el radio.
    "cerca": {
        "fondo_body": "#F5F7FA",
        "baldosa_fondo": "#FFFFFF",
        "baldosa_sombra": "none",
        "linea": "#E2E6EE",
        "atmosfera": (
            '  <span style="position: absolute; inset: 0; background: '
            'linear-gradient(160deg, #F8FAFD 0%, #F2F5FA 100%)"></span>\n  '
            + fondo_cerca() + "\n  " + velo("#F6F8FC", 430)
        ),
        "logo_filtro": "",
        "pie_color": "#4A5666",
    },
}

PIE_ARGUMENTO = """
    <div style="display: flex; align-items: center; gap: 26px; margin-top: 28px">
      {items}
    </div>
"""


def pie_argumento(color, tilde):
    puntos = ["Sin comisión por venta", "Publicar es gratis", "Tus horarios y tus ferias"]
    trozos = []
    for i, texto in enumerate(puntos):
        if i:
            trozos.append('<span style="width: 4px; height: 4px; border-radius: 999px; background: %s"></span>'
                          % ("rgba(255,255,255,.38)" if "255" in color else "#C9D0E0"))
        trozos.append(
            f'<span style="display: inline-flex; align-items: center; gap: 8px; font-size: 13px; color: {color}">'
            f'<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="{tilde}" stroke-width="1.9" '
            f'stroke-linecap="round" stroke-linejoin="round"><path d="m5.5 12.4 4.2 4.2 8.8-9.2"/></svg>{texto}</span>'
        )
    return PIE_ARGUMENTO.format(items="\n      ".join(trozos))


def pantalla(modo, archivo, pantalla_tipo, comentario,
             ancho=1440, alto_min=940, movil=False):
    cfg = FONDOS[modo]
    atmosfera = (fondo_foto(marcador=not movil) if modo == "foto"
                 else cfg["atmosfera"])
    tilde = "#6FC79A" if modo == "foto" else "#1F7A4D"

    if pantalla_tipo == "registro":
        cuerpo = FICHA_ROL + CAMPOS_REGISTRO
        caja = tarjeta(modo, "Crear cuenta", "Sumate a los emprendimientos de tu ciudad.",
                       "crear", cuerpo,
                       '¿Ya tenés una cuenta? <a href="#" style="font-weight: 600">Iniciá sesión</a>')
    else:
        caja = tarjeta(modo, "Entrá a tu cuenta",
                       "Para publicar, guardar favoritos y responder presupuestos.",
                       "entrar", CAMPOS_ENTRAR,
                       '¿Todavía no tenés cuenta? <a href="#" style="font-weight: 600">Registrate gratis</a>')

    if movil:
        caja = (caja
                # La tarjeta ya no va pegada a los bordes: 20 px de margen a
                # cada lado la despegan de la pantalla y dejan ver la foto.
                # box-sizing es lo que faltaba: con el content-box por
                # defecto, el width:100% de la tarjeta era el ancho de la
                # columna Y ADEMÁS le sumaba sus propios 18 px de padding y el
                # borde, así que se comía los 20 px de margen y quedaba pegada
                # a los dos bordes de la pantalla.
                .replace("max-width: 468px; padding: 36px 40px 32px",
                         "box-sizing: border-box; padding: 24px 18px 22px")
                .replace("border-radius: 26px", "border-radius: 22px")
                .replace("font-size: 29px", "font-size: 24px")
                # Los textos de las fichas de rol se acortan: con los largos de
                # escritorio una caía en dos renglones y la otra en tres, y las
                # dos fichas quedaban de distinto alto.
                .replace("Busco, guardo favoritos y pido presupuestos.",
                         "Busco y pido presupuestos.")
                .replace("Publico mi emprendimiento, horarios y ferias.",
                         "Publico lo que hago.")
                # Y las dos ayudas de la contraseña pasan a una sola línea: en
                # 390 px la segunda se partía y desalineaba el bloque.
                .replace("Al menos 8 caracteres", "8 caracteres o más")
                .replace("No es una de las obvias", "Nada obvio")
                # El aire interno se afina para que entre todo sin apretarse.
                .replace("margin: 10px 0 24px", "margin: 8px 0 20px")
                .replace("margin-bottom: 24px; border-radius: 13px; background: #F5F7FA",
                         "margin-bottom: 20px; border-radius: 13px; background: #F5F7FA")
                .replace("padding: 11px 0; border-radius: 10px",
                         "padding: 13px 0; border-radius: 10px"))
        relleno = "40px 20px 34px"
        alto_logo = 30
        pie = ('\n    <p style="margin: 18px 0 0; font-size: 12.5px; line-height: 1.5; color: '
               f'{cfg["pie_color"]}; text-align: center">Publicar es gratis y no cobramos '
               "comisión por venta.</p>\n")
    else:
        relleno = "54px 24px 62px"
        alto_logo = 38
        pie = pie_argumento(cfg["pie_color"], tilde)

    html = CABEZA.format(**{k: cfg[k] for k in ("fondo_body", "baldosa_fondo", "baldosa_sombra", "linea")})
    html += f"""
<!-- {comentario} -->
<div style="position: relative; width: {ancho}px; min-height: {alto_min}px; background: {cfg['fondo_body']}; overflow: hidden">
{atmosfera}
  <div style="position: relative; display: flex; flex-direction: column; align-items: center; padding: {relleno}">

    <a href="#" style="display: block; margin-bottom: 28px">
      <img src="logo-impulsar.png" alt="IMPULSAR" style="height: {alto_logo}px; width: auto; display: block;{cfg['logo_filtro']}">
    </a>
{caja}
{pie}
  </div>
</div>
</x-dc>
</body>
</html>
"""
    (AQUI / archivo).write_text(html, encoding="utf-8")
    return archivo


if __name__ == "__main__":
    hechos = [
        pantalla("foto", "Main.dc.html", "registro",
                 "CREAR CUENTA sobre foto semioscura. La foto es un hueco marcado "
                 "hasta que llegue la imagen de verdad."),
        pantalla("foto", "Entrar.dc.html", "entrar",
                 "ENTRAR sobre la misma foto. Con el error puesto.", alto_min=760),
        pantalla("foto", "MainMovil.dc.html", "registro",
                 "CREAR CUENTA EN TELEFONO: la misma foto, recortada por object-fit.",
                 ancho=390, alto_min=844, movil=True),
        # Los tres fondos dibujados quedan generados como respaldo, por si la
        # foto no aparece o no termina de convencer.
        pantalla("impulso", "Impulso.dc.html", "registro",
                 'RESPALDO A "Impulso": la barra del logo puesta en ritmo.'),
        pantalla("mendoza", "Mendoza.dc.html", "registro",
                 'RESPALDO B "Mendoza": las curvas de nivel de la montana.'),
        pantalla("cerca", "Cerca.dc.html", "registro",
                 'RESPALDO C "Cerca tuyo": el plano con los anillos de radio.'),
    ]
    print("generados:", ", ".join(hechos))
