let ALL_POSTS = [];

// Utilidad básica para evitar inyección de HTML
function escapeHtml(str) {
    return String(str || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// El corazon de favorito de una tarjeta de la home.
//
// Es el mismo <form> POST con CSRF que arma partials/_favorito_boton.html en el
// servidor, y no un fetch: asi el toggle sigue siendo una sola ruta
// (blog.toggle_favorite), que ya redirige de vuelta a donde estabas. El token
// sale del <meta name="csrf-token"> de base.html, que es el de la sesion.
function botonFavorito(post, title) {
    const token = document.querySelector('meta[name="csrf-token"]');
    if (!token) return "";

    const activo = post.favorito;
    const etiqueta = activo ? "Quitar de favoritos" : "Agregar a favoritos";

    return `
        <form method="post" action="/blog/${post.id}/favorito" class="favorite-form">
            <input type="hidden" name="csrf_token" value="${escapeHtml(token.content)}">
            <button type="submit" class="favorite-btn ${activo ? "favorite-btn--active" : ""}"
                aria-pressed="${activo ? "true" : "false"}"
                aria-label="${etiqueta} ${title}"
                title="${etiqueta}">${activo ? "♥" : "♡"}</button>
        </form>
    `;
}

function renderPosts(posts) {
    const grid = document.getElementById("posts-grid");
    const emptyEl = document.getElementById("posts-empty");

    if (!grid) return;

    grid.innerHTML = "";

    if (!posts || posts.length === 0) {
        emptyEl.style.display = "block";
        return;
    } else {
        emptyEl.style.display = "none";
    }

    posts.forEach((post) => {
        const card = document.createElement("article");
        card.className = "card";

        const title = escapeHtml(post.title || "Emprendimiento sin título");
        const body = escapeHtml(post.body || "");
        // 160, el mismo recorte que usa la tarjeta del listado.
        const shortBody = body.length > 160 ? body.slice(0, 160) + "..." : body;

        // La tarjeta es la misma .tarjeta que arma el listado en el servidor
        // (ver app/blog/templates/blog/index.html), en su variante vertical: la
        // home y /blog/ tienen que verse iguales.
        //
        // Solo se pinta lo que la API devuelve de verdad. El artboard "Inicio"
        // muestra ademas "abierto ahora", el barrio y los km: los horarios y
        // las coordenadas existen en la base, pero hoy no viajan por fila
        // (habria que sumarlos al select de /api/posts/) y sin geolocalizar no
        // hay distancia que calcular. Nada de eso se dibuja inventado.
        const postDetailUrl = `/blog/${post.id}`;
        const postAbsoluteUrl = `${location.origin}${postDetailUrl}`;
        const postImageUrl = post.image ? `/static/uploads/${escapeHtml(post.image)}` : null;
        const categoryText = escapeHtml(post.category_label || "Sin categoría");
        const categoryKey = escapeHtml(post.category || "otros");

        card.className = "tarjeta tarjeta--vertical";

        const imagenHtml = postImageUrl
            ? `<img src="${postImageUrl}" alt="" class="tarjeta__img" loading="lazy">`
            : "";

        // El corazon solo existe si la API mando "favorito", o sea si hay
        // sesion. Sin login no se dibuja un boton que iba a rebotar al login.
        const favoritoHtml =
            typeof post.favorito === "boolean" ? botonFavorito(post, title) : "";

        // Sin reseñas se dice "Sin reseñas todavía" y no un 0: es lo mismo que
        // hace el listado, y un cero se leeria como una mala calificacion.
        const ratingHtml = post.avg_rating
            ? `<span class="dato dato--rating"
                     aria-label="Calificación promedio: ${post.avg_rating} de 5">
                   <span class="dato__estrella" aria-hidden="true">★</span>
                   ${post.avg_rating} · ${post.review_count}
                   reseña${post.review_count === 1 ? "" : "s"}
               </span>`
            : `<span class="dato">Sin reseñas todavía</span>`;

        // El pie con la persona detras del emprendimiento: es uno de los cinco
        // datos que el rediseño pide adelante (ver disenio-inicio/DISENIO.md).
        //
        // Las iniciales se recortan del nombre CRUDO y recien despues se
        // escapan. Al reves -- escapar y cortar dos caracteres -- un nombre que
        // empieza con &, <, " o ' deja media entidad ("&a", "&l") pintada en el
        // circulo. Es el mismo orden que usa el listado, que hace
        // username[:2] | upper y deja escapar a Jinja.
        const autorCrudo = post.author_name || "";
        const autor = escapeHtml(autorCrudo);
        const iniciales = escapeHtml(autorCrudo.slice(0, 2).toUpperCase());
        const pieHtml = autorCrudo
            ? `<span class="tarjeta__persona">
                   <span class="tarjeta__avatar" aria-hidden="true">${iniciales}</span>
                   ${autor}
               </span>`
            : "<span></span>";

        card.innerHTML = `
            <a href="${postDetailUrl}" class="tarjeta__foto" tabindex="-1" aria-hidden="true">
                ${imagenHtml}
            </a>
            <span class="rubro-pastilla rubro-pastilla--${categoryKey} tarjeta__sello">
                ${categoryText}
            </span>
            <div class="tarjeta__acciones tarjeta__acciones--sobre-foto">
                <button type="button" class="share-btn"
                    data-share-url="${postAbsoluteUrl}"
                    data-share-title="${title}"
                    aria-label="Compartir ${title}"
                    title="Compartir">🔗</button>
                ${favoritoHtml}
            </div>
            <div class="tarjeta__cuerpo">
                <div class="tarjeta__datos">${ratingHtml}</div>
                <h3 class="tarjeta__titulo">
                    <a href="${postDetailUrl}">${title}</a>
                </h3>
                <p class="tarjeta__desc">${shortBody}</p>
                <div class="tarjeta__pie">
                    ${pieHtml}
                    <a href="${postDetailUrl}" class="btn btn--secondary btn--chico">Ver</a>
                </div>
            </div>
        `;

        grid.appendChild(card);
    });
}
// Pide los emprendimientos al servidor. La busqueda se resuelve en la base de
// datos y no en el navegador: antes se descargaban TODOS los posts y se
// filtraban aca, lo que deja de funcionar apenas la plataforma crezca.
function fetchPosts(query, categoria) {
    const params = new URLSearchParams();
    if (query) params.set("q", query);
    // La API ignora una categoria que no existe, asi que no hace falta
    // validarla aca: alcanza con no mandar el parametro vacio.
    if (categoria) params.set("category", categoria);
    params.set("per_page", "12");

    return fetch(`/api/posts/?${params.toString()}`).then((res) => {
        if (!res.ok) throw new Error("Error al obtener los posts");
        return res.json();
    });
}

// Evita disparar una consulta por cada tecla que se aprieta.
function debounce(fn, ms) {
    let timeoutId;
    return (...args) => {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => fn(...args), ms);
    };
}

document.addEventListener("DOMContentLoaded", () => {
    const grid = document.getElementById("posts-grid");
    const errorEl = document.getElementById("posts-error");
    const loadingEl = document.getElementById("posts-loading");
    const searchForm = document.getElementById("search-form");
    const input = document.getElementById("search-text");
    const selectCategoria = document.getElementById("search-category");
    const cerca = document.getElementById("search-near");
    const lat = document.getElementById("search-lat");
    const lon = document.getElementById("search-lon");
    const botonCerca = document.getElementById("use-my-location-home");

    if (!grid) return; // no estamos en la home

    function cargar(query, categoria) {
        // En conexiones lentas la grilla queda vacia varios segundos sin este
        // aviso, y parece que la pagina no respondio.
        if (errorEl) errorEl.style.display = "none";
        if (loadingEl) loadingEl.style.display = "block";
        grid.innerHTML = "";

        fetchPosts(query, categoria)
            .then((data) => {
                ALL_POSTS = Array.isArray(data.items) ? data.items : [];
                renderPosts(ALL_POSTS);
            })
            .catch((err) => {
                console.error(err);
                if (errorEl) errorEl.style.display = "block";
            })
            .finally(() => {
                if (loadingEl) loadingEl.style.display = "none";
            });
    }

    // Los dos campos del buscador se leen juntos: filtrar por rubro no tiene
    // que perder lo que el usuario ya habia escrito, ni al reves.
    function cargarDesdeElFormulario() {
        cargar(
            input ? input.value.trim() : "",
            selectCategoria ? selectCategoria.value : ""
        );
    }

    // Si hay ubicacion, la busqueda se va al listado: es la unica pantalla que
    // ordena por distancia (consultas.buscar_posts la calcula en SQL). La home
    // filtra en vivo, pero no sabe de kilometros.
    function hayUbicacion() {
        return Boolean((cerca && cerca.value.trim()) || (lat && lat.value));
    }

    function irAlListadoConUbicacion() {
        const params = new URLSearchParams();
        const texto = input ? input.value.trim() : "";
        const categoria = selectCategoria ? selectCategoria.value : "";

        // Lo que el usuario ya habia cargado viaja con el; /blog/ lee los
        // mismos tres nombres (ver formulario.leer_busqueda, leer_cercania y
        // leer_categoria_de_filtro).
        if (texto) params.set("q", texto);
        if (categoria) params.set("category", categoria);

        if (lat && lat.value && lon && lon.value) {
            // Coordenadas del navegador: no hace falta geocodificar nada.
            params.set("lat", lat.value);
            params.set("lon", lon.value);
        } else if (cerca) {
            params.set("near", cerca.value.trim());
        }

        window.location.href = `/blog/?${params.toString()}`;
    }

    cargar("", "");

    // Si retoca la direccion a mano, las coordenadas de "Cerca de mí" quedan
    // viejas: sin esto el servidor usaria esas en vez del texto nuevo. Es el
    // mismo cuidado que ya tiene el buscador del listado.
    if (cerca) {
        cerca.addEventListener("input", () => {
            if (lat) lat.value = "";
            if (lon) lon.value = "";
        });
    }

    if (botonCerca) {
        botonCerca.addEventListener("click", () => {
            if (!navigator.geolocation) {
                alert("Tu navegador no soporta geolocalización.");
                return;
            }

            // Se escribe sobre el <span> del texto y no sobre el boton entero:
            // el boton lleva adentro el SVG del pin, y un textContent en el
            // boton lo borraria para siempre.
            const etiqueta =
                botonCerca.querySelector(".buscador__cerca-texto") || botonCerca;
            const textoOriginal = etiqueta.textContent;
            botonCerca.disabled = true;
            etiqueta.textContent = "Ubicando...";

            navigator.geolocation.getCurrentPosition(
                (posicion) => {
                    if (lat) lat.value = posicion.coords.latitude;
                    if (lon) lon.value = posicion.coords.longitude;
                    irAlListadoConUbicacion();
                },
                () => {
                    alert("No pudimos acceder a tu ubicación.");
                    botonCerca.disabled = false;
                    etiqueta.textContent = textoOriginal;
                }
            );
        });
    }

    if (searchForm) {
        searchForm.addEventListener("submit", (e) => {
            e.preventDefault();
            if (hayUbicacion()) {
                irAlListadoConUbicacion();
                return;
            }
            cargarDesdeElFormulario();
        });

        if (input) {
            input.addEventListener(
                "input",
                debounce(cargarDesdeElFormulario, 300)
            );
        }

        // El select no pasa por el debounce: elegir un rubro es un solo gesto
        // deliberado, no una tecla atras de otra.
        if (selectCategoria) {
            selectCategoria.addEventListener("change", cargarDesdeElFormulario);
        }
    }
});
// =============================
// SWITCH DE TEMA (CLARO / OSCURO)
// =============================
// El tema inicial ya lo resolvio el script inline del <head> de base.html
// (tiene que correr antes del primer pintado para que no parpadee). Aca solo
// esta el switch: cambiar el atributo, persistir la eleccion y mantener el
// estado accesible del boton.
const TEMA_STORAGE_KEY = "impulsar-tema";

function temaGuardado() {
    try {
        const valor = localStorage.getItem(TEMA_STORAGE_KEY);
        return valor === "dark" || valor === "light" ? valor : null;
    } catch (e) {
        return null; // modo privado / cookies bloqueadas
    }
}

function aplicarTema(tema, boton) {
    document.documentElement.setAttribute("data-theme", tema);
    if (boton) boton.setAttribute("aria-pressed", tema === "dark" ? "true" : "false");
}

document.addEventListener("DOMContentLoaded", () => {
    const boton = document.getElementById("theme-toggle");
    if (!boton) return;

    const temaActual = document.documentElement.getAttribute("data-theme") || "light";
    boton.setAttribute("aria-pressed", temaActual === "dark" ? "true" : "false");

    boton.addEventListener("click", () => {
        const nuevo =
            document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
        aplicarTema(nuevo, boton);
        try {
            // A partir del primer click la eleccion manual pisa al sistema
            // operativo, incluso si despues el SO cambia de tema.
            localStorage.setItem(TEMA_STORAGE_KEY, nuevo);
        } catch (e) {
            // Sin persistencia el tema igual cambia, pero solo en esta pagina.
        }
    });

    // Mientras el usuario nunca haya tocado el switch, seguimos al sistema en
    // vivo: si cambia el tema del SO con la pestaña abierta, la pagina acompaña.
    const consultaSO = window.matchMedia("(prefers-color-scheme: dark)");
    consultaSO.addEventListener("change", (evento) => {
        if (temaGuardado()) return; // hay eleccion explicita: no la pisamos
        aplicarTema(evento.matches ? "dark" : "light", boton);
    });
});

// =============================
// MENÚ DE LA CUENTA EN LA BARRA
// =============================
document.addEventListener("DOMContentLoaded", () => {
    const boton = document.getElementById("user-menu-toggle");
    const menu = document.getElementById("user-menu");
    if (!boton || !menu) return; // no hay sesion: no existe el avatar

    function cerrar() {
        menu.classList.remove("menu-cuenta--abierto");
        boton.setAttribute("aria-expanded", "false");
    }

    boton.addEventListener("click", (evento) => {
        evento.stopPropagation();
        const abierto = menu.classList.toggle("menu-cuenta--abierto");
        boton.setAttribute("aria-expanded", abierto ? "true" : "false");
    });

    // Un click adentro del menu no lo cierra: son nueve links y uno de ellos
    // puede estar abajo del todo, con el menu scrolleado.
    menu.addEventListener("click", (evento) => evento.stopPropagation());

    document.addEventListener("click", cerrar);

    // Escape cierra y devuelve el foco al avatar: el menu se abre con teclado
    // igual que con el mouse, y sin esto quedaria abierto y sin salida.
    document.addEventListener("keydown", (evento) => {
        if (evento.key !== "Escape") return;
        if (!menu.classList.contains("menu-cuenta--abierto")) return;
        cerrar();
        boton.focus();
    });
});

// La hamburguesa se fue con el rediseño de navegacion: en telefono la
// navegacion es la barra de pestañas de abajo (partials/_tabbar.html), que es
// marcado y CSS, sin JS que la abra ni la cierre.

// =============================
// CONTADORES DE LA NAVEGACIÓN
// =============================
// Un numero por item y no un total pegado a "Mensajes". El endpoint ya devolvia
// las tres claves por separado; lo que sumaba era esto. Cada elemento dice cual
// quiere con data-notif, y el mismo contador puede aparecer en varios lugares a
// la vez (el sobre de la barra, la pestaña del telefono, el menu de la cuenta).
document.addEventListener("DOMContentLoaded", () => {
    const contadores = document.querySelectorAll("[data-notif]");
    if (!contadores.length) return; // no esta logueado

    function pintar(elemento, cantidad) {
        if (cantidad > 0) {
            elemento.textContent = cantidad > 9 ? "9+" : String(cantidad);
            elemento.hidden = false;
        } else {
            elemento.hidden = true;
        }
    }

    function actualizar() {
        fetch("/mensajes/notificaciones")
            .then((res) => (res.ok ? res.json() : Promise.reject(res)))
            .then((datos) => {
                contadores.forEach((elemento) => {
                    pintar(elemento, datos[elemento.dataset.notif] || 0);
                });
            })
            .catch(() => {
                // Un polling fallido no debe romper la navegacion normal.
            });
    }

    actualizar();
    setInterval(actualizar, 20000);
});

// =============================
// BÚSQUEDA POR CERCANÍA (listado de emprendimientos)
// =============================
document.addEventListener("DOMContentLoaded", () => {
    const boton = document.getElementById("use-my-location");
    const nearInput = document.getElementById("near-input");
    const latInput = document.getElementById("near-lat");
    const lonInput = document.getElementById("near-lon");

    if (!boton || !nearInput || !latInput || !lonInput) return; // no estamos en /blog/

    // Si el usuario retoca el texto a mano, las coordenadas anteriores (de
    // "Mi ubicación" o de una busqueda previa) quedan obsoletas: sin esto, el
    // servidor las usaria en vez de geocodificar el texto nuevo.
    nearInput.addEventListener("input", () => {
        latInput.value = "";
        lonInput.value = "";
    });

    boton.addEventListener("click", () => {
        if (!navigator.geolocation) {
            alert("Tu navegador no soporta geolocalización.");
            return;
        }

        const textoOriginal = boton.textContent;
        boton.disabled = true;
        boton.textContent = "Ubicando...";

        navigator.geolocation.getCurrentPosition(
            (posicion) => {
                latInput.value = posicion.coords.latitude;
                lonInput.value = posicion.coords.longitude;
                nearInput.value = "";
                // El form que se manda es EL DEL CAMPO, no el que envuelve al
                // boton: desde el rediseño de la barra de filtros, "Cerca de
                // mí" vive en la fila de fichas, afuera del <form>, así que
                // `boton.closest("form")` daba null y el click moría con un
                // TypeError sin buscar nada. Y aunque el botón estuviera dentro
                // de algún form, el que tiene que viajar es el que lleva las
                // coordenadas que se acaban de escribir.
                latInput.form.submit();
            },
            () => {
                alert("No pudimos acceder a tu ubicación.");
                boton.disabled = false;
                boton.textContent = textoOriginal;
            }
        );
    });
});

/* Plantillas de respuesta (detalle de una solicitud de presupuesto).

   Escriben en un textarea de la misma pagina; no hay nada del servidor de por
   medio. El bloque viene con `hidden` desde el template y se destapa aca: si
   el navegador no corre este archivo, no quedan tres botones que no hacen
   nada. Es el mismo criterio del boton "Mi ubicación" de la busqueda. */
document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-plantillas-de]").forEach((bloque) => {
        const destino = document.getElementById(bloque.dataset.plantillasDe);
        if (!destino) return;

        bloque.hidden = false;

        bloque.querySelectorAll(".plantillas__opcion").forEach((opcion) => {
            opcion.addEventListener("click", () => {
                const texto = opcion.dataset.texto || "";
                const actual = destino.value.trim();

                // Se agrega, no se pisa: quien ya escribio algo esta usando la
                // plantilla como remate, no como reemplazo.
                destino.value = actual ? `${actual} ${texto}` : texto;
                destino.focus();
                destino.setSelectionRange(destino.value.length, destino.value.length);
            });
        });
    });
});


/* Contador de caracteres (formulario de emprendimiento).

   El bloque viene con `hidden` desde el template y se destapa aca, igual que
   las plantillas de respuesta: sin JS no queda un contador clavado en cero.
   El tope lo pone el maxlength del campo, que sale del largo real de la
   columna; aca no hay ningun numero escrito. */
document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-contador-de]").forEach((contador) => {
        const campo = document.getElementById(contador.dataset.contadorDe);
        const valor = contador.querySelector(".contador__valor");
        if (!campo || !valor) return;

        contador.hidden = false;

        const actualizar = () => {
            valor.textContent = campo.value.length;
        };

        campo.addEventListener("input", actualizar);
        actualizar();
    });
});


/* Vista previa en vivo de la tarjeta del emprendimiento.

   Refleja lo que se esta escribiendo; no guarda nada ni consulta nada. Los
   textos de arranque los pinta el servidor (el post que se edita, o el
   placeholder en el alta), asi que sin JS la tarjeta igual dice algo
   coherente: lo unico que se pierde es que acompañe mientras se tipea. */
document.addEventListener("DOMContentLoaded", () => {
    const previa = document.querySelector(".vista-previa");
    if (!previa) return;

    const espejo = (idCampo, selector, recorte) => {
        const campo = document.getElementById(idCampo);
        const destino = previa.querySelector(selector);
        if (!campo || !destino) return;

        // El texto que ya esta puesto es el que corresponde cuando el campo
        // esta vacio: se guarda para poder volver a el si lo borran.
        const porDefecto = destino.textContent.trim();

        campo.addEventListener("input", () => {
            const texto = campo.value.trim();
            if (!texto) {
                destino.textContent = porDefecto;
                return;
            }
            destino.textContent =
                recorte && texto.length > recorte ? `${texto.slice(0, recorte)}…` : texto;
        });
    };

    espejo("title", '[data-previa="titulo"]');
    espejo("body", '[data-previa="descripcion"]', 110);

    // La categoria son radios: se escucha el cambio en el grupo y se copia la
    // etiqueta visible del elegido, que es exactamente lo que muestra el chip.
    const destinoCategoria = previa.querySelector('[data-previa="categoria"]');
    if (destinoCategoria) {
        document.querySelectorAll('input[name="category"]').forEach((radio) => {
            radio.addEventListener("change", () => {
                if (!radio.checked) return;
                const cara = radio.parentElement.querySelector(".chip-radio__cara");
                if (cara) destinoCategoria.textContent = cara.textContent.trim();
            });
        });
    }
});


/* Confirmacion de los formularios destructivos (borrar, banear).

   El texto viaja en data-confirm y el confirm() se arma aca, en vez de ir
   escrito adentro de un onsubmit="return confirm('...')" en el template.
   No es cosmetico: ese patron era un XSS almacenado. Jinja escapa la comilla
   simple de un titulo a &#39;, pero el parser HTML decodifica las entidades
   del atributo ANTES de compilar el handler, asi que la comilla volvia a
   aparecer del lado de JS y cerraba el string. Un emprendimiento llamado
   X' + (codigo) + ' terminaba ejecutando ese codigo en la sesion del admin
   que apretaba Eliminar.

   Un atributo data- no tiene ese problema porque nunca se compila como JS:
   el navegador lo decodifica una sola vez y queda como texto en el dataset.

   Es un listener delegado en document y no uno por formulario, para que
   tambien valga para lo que se agregue al DOM despues. Si el usuario
   cancela, se frena el submit; sin JS no hay confirmacion y el formulario
   manda directo, igual que antes (el onsubmit inline tampoco corria). */
document.addEventListener("submit", (evento) => {
    const formulario = evento.target.closest("form[data-confirm]");
    if (!formulario) return;

    if (!window.confirm(formulario.dataset.confirm)) {
        evento.preventDefault();
    }
});


/* La barra de filtros del listado se compacta en telefono.

   Los tres campos apilados ocupaban 310 px y empujaban el primer resultado
   abajo del doblez, que es lo contrario de lo que tiene que hacer una pantalla
   de resultados. Van adentro de un <details> que arranca con `open` en el HTML
   a proposito: sin JS queda desplegado, que es peor pero nunca roto.

   Se cierra una sola vez, al cargar, y no se reabre ni se recierra al girar el
   telefono: si el usuario lo abrio para cargar una direccion, un resize (que en
   Android dispara el teclado virtual) no puede cerrarselo en la cara. */
(() => {
    const desplegable = document.querySelector(".barra-filtros__desplegable");
    if (!desplegable) return;

    if (window.matchMedia("(max-width: 860px)").matches) {
        desplegable.open = false;
    }
})();

/* Lo mismo con la columna de filtros de la busqueda de servicios, que en
   telefono tiene el mismo problema: trece rubros, la zona, el precio y el
   interruptor empujan la primera ficha fuera de la pantalla.

   El corte son 879 px y no 860 porque es donde .explorar deja de ser dos
   columnas: hasta ahi la columna esta al costado y no estorba. */
(() => {
    const columna = document.querySelector(".filtros__desplegable--columna");
    if (!columna) return;

    if (window.matchMedia("(max-width: 879px)").matches) {
        columna.open = false;
    }
})();

// El ojo que muestra la contraseña, en entrar y crear cuenta.
//
// Va en su propio listener y no adentro del de arriba a proposito: aquel corta
// con `if (!grid) return` apenas ve que no esta en la home, que es justo el
// caso de las pantallas de auth.
//
// El boton se dibuja escondido (ver auth/_ojo.html) y lo enciende ESTE codigo:
// si el JS no carga, no queda un boton pintado que no responde.
document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-ojo]").forEach((boton) => {
        const campo = document.getElementById(boton.dataset.ojo);
        if (!campo) return;

        boton.hidden = false;

        boton.addEventListener("click", () => {
            const seVe = campo.type === "text";
            campo.type = seVe ? "password" : "text";
            boton.setAttribute("aria-pressed", seVe ? "false" : "true");

            const etiqueta = seVe ? "Mostrar la contraseña" : "Ocultar la contraseña";
            boton.setAttribute("aria-label", etiqueta);
            boton.title = etiqueta;

            // El foco vuelve al campo y el cursor al final: si no, apretar el
            // ojo para revisar lo que se escribio obliga a volver a clickear
            // adentro para seguir escribiendo.
            const largo = campo.value.length;
            campo.focus();
            campo.setSelectionRange(largo, largo);
        });
    });
});


// Las pestañas del perfil (emprendimientos / ferias y eventos).
//
// Mismo criterio que el ojo de arriba: la barra se dibuja con `hidden` y la
// enciende ESTE codigo. Sin JS las dos secciones quedan una abajo de la otra,
// que es como funcionaba el perfil antes de las pestañas; nadie se queda con
// medio perfil invisible porque no cargo un script.
document.addEventListener("DOMContentLoaded", () => {
    const barra = document.querySelector("[data-perfil-tabs]");
    if (!barra) return;

    const botones = Array.from(barra.querySelectorAll("[data-perfil-tab]"));
    const paneles = new Map();
    botones.forEach((boton) => {
        const panel = document.querySelector(
            `[data-perfil-panel="${boton.dataset.perfilTab}"]`
        );
        if (panel) paneles.set(boton, panel);
    });

    // Con una sola seccion no hay nada que elegir: la barra se queda escondida
    // y la seccion a la vista. Pasa en el perfil de quien no publico eventos.
    if (paneles.size < 2) return;

    barra.hidden = false;

    const mostrar = (elegido) => {
        paneles.forEach((panel, boton) => {
            const activo = boton === elegido;
            boton.classList.toggle("perfil-tabs__boton--activo", activo);
            boton.setAttribute("aria-pressed", activo ? "true" : "false");
            panel.hidden = !activo;
        });
    };

    botones.forEach((boton) => {
        boton.addEventListener("click", () => mostrar(boton));
    });

    mostrar(botones[0]);
});


// Los plegables que solo se pliegan en telefono: la semana de horarios y el
// mapa de la lateral.
//
// En escritorio la lateral es una columna al costado y esas dos cosas entran
// sin molestar; en telefono cae abajo de todo y son ~350px de scroll que nadie
// pidio. El `open` viaja en el HTML, asi que sin JS quedan abiertos en los dos
// tamaños (que es como estaban): esto solo los cierra cuando la pantalla es
// angosta.
document.addEventListener("DOMContentLoaded", () => {
    const plegables = Array.from(document.querySelectorAll("[data-plegar-en-movil]"));
    if (!plegables.length) return;

    const angosta = window.matchMedia("(max-width: 960px)");

    const aplicar = () => {
        plegables.forEach((plegable) => {
            plegable.open = !angosta.matches;
        });
    };

    aplicar();
    angosta.addEventListener("change", aplicar);

    // maplibre mide el contenedor cuando se crea. Si nace adentro de un
    // <details> cerrado mide 0 y el mapa queda en blanco al abrirlo, asi que
    // se le avisa: el mapa escucha el resize de la ventana (trackResize viene
    // prendido por defecto) y se vuelve a medir solo.
    plegables.forEach((plegable) => {
        if (!plegable.querySelector("#map")) return;
        plegable.addEventListener("toggle", () => {
            if (plegable.open) window.dispatchEvent(new Event("resize"));
        });
    });
});


// La barra de guardar de Ajustes: dice si hay cambios sin guardar.
//
// El formulario del perfil se puede recorrer entero sin saber si se tocó algo,
// y lo que está en pantalla no lo ve nadie hasta que se guarda. La barra nace
// diciendo "Todo guardado" desde el HTML (que es lo cierto al entrar) y este
// código la cambia al primer cambio. Sin JS queda el texto de arranque y el
// botón, que es exactamente lo que había antes.
document.addEventListener("DOMContentLoaded", () => {
    const formulario = document.querySelector("[data-ajustes-form]");
    if (!formulario) return;

    const barra = formulario.querySelector("[data-ajustes-barra]");
    if (!barra) return;

    const titulo = barra.querySelector("[data-barra-titulo]");
    const detalle = barra.querySelector("[data-barra-detalle]");
    const detalleOriginal = detalle ? detalle.textContent.trim() : "";
    let sucio = false;

    const ensuciar = () => {
        if (sucio) return;
        sucio = true;
        barra.classList.add("ajustes-guardar--sucia");
        if (titulo) titulo.textContent = "Tenés cambios sin guardar";
        if (detalle) detalle.textContent = "Nadie los ve hasta que toques Guardar.";
    };

    // "change" y no solo "input": los que valen para las fotos y los
    // interruptores son cambios de checkbox y de <input type=file>, que no
    // disparan "input" en todos los navegadores.
    formulario.addEventListener("input", ensuciar);
    formulario.addEventListener("change", ensuciar);

    // Al mandar, la barra deja de avisar: si no, el navegador todavía muestra
    // la pantalla vieja mientras carga la nueva y el aviso queda mintiendo.
    formulario.addEventListener("submit", () => {
        sucio = true;  // evita que un "input" tardío lo vuelva a pintar
        barra.classList.remove("ajustes-guardar--sucia");
        if (titulo) titulo.textContent = "Guardando…";
        if (detalle) detalle.textContent = detalleOriginal;
    });
});


// La vista previa del perfil, mientras se escribe.
//
// Es la mitad del rediseño de Ajustes: antes se escribía a ciegas y había que
// salir al perfil para ver cómo quedaba. La previa se dibuja en el servidor
// con lo guardado (así también existe sin JS); esto solo la va acompañando.
document.addEventListener("DOMContentLoaded", () => {
    const bio = document.querySelector('[data-previa-origen="bio"]');
    const previaBio = document.querySelector("[data-previa-bio]");
    const contador = document.querySelector("[data-contador]");

    if (bio && (previaBio || contador)) {
        const vacia = "Todavía no escribiste tu biografía.";

        const pintar = () => {
            const texto = bio.value.trim();

            if (previaBio) {
                // textContent y no innerHTML: lo que se escribe es texto de la
                // persona y acá no se renderiza el markdown (eso lo hace el
                // servidor con render_bio al guardar). Meterlo como HTML sería
                // ejecutar lo que se escriba en el campo.
                previaBio.textContent = texto || vacia;
                previaBio.classList.toggle("ajustes-previa__bio--vacia", !texto);
            }
            if (contador) {
                contador.hidden = false;
                contador.textContent = `${bio.value.length} caracteres`;
            }
        };

        bio.addEventListener("input", pintar);
        pintar();
    }

    const ubicacion = document.querySelector('[data-previa-origen="ubicacion"]');
    const chip = document.querySelector("[data-previa-ubicacion]");
    const chipTexto = document.querySelector("[data-previa-ubicacion-texto]");

    if (ubicacion && chip && chipTexto) {
        ubicacion.addEventListener("input", () => {
            const texto = ubicacion.value.trim();
            chipTexto.textContent = texto;
            chip.hidden = !texto;
        });
    }
});


// Los horarios: el interruptor apaga su fila, y los dos atajos hacen el
// trabajo repetido.
//
// El interruptor ES el checkbox "cerrado_N" de siempre (el backend no cambió):
// lo único que agrega el JS es apagar visualmente la fila y los dos botones de
// arriba, que nacen con `hidden` y se encienden acá. Sin JS, marcar el día
// como cerrado sigue funcionando igual.
document.addEventListener("DOMContentLoaded", () => {
    const filas = Array.from(document.querySelectorAll("[data-horario-fila]"));
    if (!filas.length) return;

    const apagar = (fila) => {
        const cerrado = fila.querySelector("[data-cerrado]");
        if (!cerrado) return;
        fila.classList.toggle("horario-fila--cerrada", cerrado.checked);
    };

    filas.forEach((fila) => {
        const cerrado = fila.querySelector("[data-cerrado]");
        if (cerrado) cerrado.addEventListener("change", () => apagar(fila));
        apagar(fila);
    });

    const atajos = document.querySelector("[data-horarios-atajos]");
    if (!atajos) return;
    atajos.hidden = false;

    const hora = (fila, cual) => fila.querySelector(`[data-hora="${cual}"]`);

    const copiar = atajos.querySelector("[data-copiar-lunes]");
    if (copiar) {
        copiar.addEventListener("click", () => {
            const lunes = filas[0];
            const abre = hora(lunes, "abre");
            const cierra = hora(lunes, "cierra");
            const cerrado = lunes.querySelector("[data-cerrado]");

            filas.slice(1).forEach((fila) => {
                if (abre) hora(fila, "abre").value = abre.value;
                if (cierra) hora(fila, "cierra").value = cierra.value;
                const suyo = fila.querySelector("[data-cerrado]");
                if (suyo && cerrado) suyo.checked = cerrado.checked;
                apagar(fila);
            });

            // A mano: cambiar .value y .checked desde código no dispara
            // "change", y la barra de guardar se quedaría diciendo que no hay
            // nada que guardar.
            atajos.dispatchEvent(new Event("change", { bubbles: true }));
        });
    }

    const finde = atajos.querySelector("[data-cerrar-finde]");
    if (finde) {
        finde.addEventListener("click", () => {
            filas.slice(5).forEach((fila) => {
                const cerrado = fila.querySelector("[data-cerrado]");
                if (cerrado) cerrado.checked = true;
                apagar(fila);
            });
            atajos.dispatchEvent(new Event("change", { bubbles: true }));
        });
    }
});


// Nuevo/editar servicio: la vista previa de la ficha y el bloque de turnos.
//
// Mismo criterio que la previa de Ajustes: la ficha se dibuja en el servidor
// con lo que hay (así existe sin JS y, al volver por un error, muestra lo que
// la persona escribió), y esto solo la va acompañando mientras se tipea.
//
// El bloque de la duración del turno nace VISIBLE en el HTML y lo esconde este
// script cuando los turnos están apagados. Al revés —nacer oculto y mostrarlo
// con JS— dejaría, sin JavaScript, un campo obligatorio que no se puede
// completar.
document.addEventListener("DOMContentLoaded", () => {
    const formulario = document.querySelector("[data-preview-servicio]");
    if (!formulario) return;

    const campo = (nombre) => formulario.querySelector(`[data-previa="${nombre}"]`);
    const enPrevia = (selector) => formulario.querySelector(selector);

    // --- el bloque de turnos
    const turnos = campo("turnos");
    const bloque = formulario.querySelector("[data-bloque-turnos]");
    const chipTurnos = enPrevia("[data-previa-chip-turnos]");

    const pintarTurnos = () => {
        if (bloque) bloque.hidden = !turnos.checked;
        if (chipTurnos) chipTurnos.hidden = !turnos.checked;
    };

    if (turnos) {
        turnos.addEventListener("change", pintarTurnos);
        pintarTurnos();
    }

    // --- los textos de la ficha
    const acompanar = (nombre, destino, vacio, claseVacia) => {
        const origen = campo(nombre);
        const nodo = enPrevia(destino);
        if (!origen || !nodo) return;

        origen.addEventListener("input", () => {
            const texto = origen.value.trim();
            // textContent y no innerHTML: es texto que escribe la persona, y
            // meterlo como HTML sería ejecutar lo que se escriba en el campo.
            nodo.textContent = texto || vacio;
            if (claseVacia) nodo.classList.toggle(claseVacia, !texto);
        });
    };

    acompanar("titulo", "[data-previa-titulo]", "El título de tu servicio",
              "servicio__titulo--vacio");
    acompanar("descripcion", "[data-previa-descripcion]",
              "La descripción aparece acá, debajo del título.", "servicio__desc--vacia");
    acompanar("zona", "[data-previa-zona]", "Sin zona", "dato--vacio");

    // --- el precio: vacío no es cero, es "a presupuestar"
    const precio = campo("precio");
    const previaPrecio = enPrevia("[data-previa-precio]");
    const previaNota = enPrevia("[data-previa-precio-nota]");

    if (precio && previaPrecio) {
        precio.addEventListener("input", () => {
            const texto = precio.value.trim();
            previaPrecio.textContent = texto || "A presupuestar";
            previaPrecio.classList.toggle("servicio__precio--abierto", !texto);
            if (previaNota) {
                previaNota.textContent = texto ? "Precio estimado" : "Le cotizás su caso";
            }
        });
    }

    // --- el rubro cambia el ícono del emblema y el chip
    const rubro = campo("rubro");
    const previaRubro = enPrevia("[data-previa-rubro]");
    const emblema = enPrevia("[data-previa-emblema]");

    if (rubro) {
        rubro.addEventListener("change", () => {
            if (previaRubro) {
                previaRubro.textContent =
                    rubro.options[rubro.selectedIndex].textContent.trim();
            }
            if (emblema) {
                // Los trece íconos ya están en el HTML (el marcado vive en las
                // plantillas, ver partials/_icono_oficio.html): acá solo se
                // muestra el que corresponde.
                emblema.querySelectorAll("[data-oficio]").forEach((icono) => {
                    icono.hidden = icono.dataset.oficio !== rubro.value;
                });
            }
        });
    }

    // --- apagado: la ficha se ve como se va a ver, es decir, no se ve
    const disponible = campo("disponible");
    const ficha = enPrevia("[data-previa-ficha]");
    const nota = enPrevia("[data-previa-oculto]");

    if (disponible && ficha) {
        disponible.addEventListener("change", () => {
            ficha.classList.toggle("servicio--apagado", !disponible.checked);
            if (nota) nota.hidden = disponible.checked;
        });
    }
});


// Reservar un turno: el resumen del costado sigue al horario elegido.
//
// El horario es un <input type="radio"> adentro del formulario que confirma, y
// el resumen nace diciendo "elegí uno de los horarios libres" desde el HTML.
// Esto solo lo va completando. SIN JAVASCRIPT LA PANTALLA FUNCIONA IGUAL: el
// radio se marca, el botón envía y la vista rechaza con "Elegí un horario de la
// lista" si no se eligió ninguno; lo único que falta es ver el turno escrito
// antes de confirmar.
document.addEventListener("DOMContentLoaded", () => {
    const resumen = document.querySelector("[data-resumen-turno]");
    if (!resumen) return;

    const fecha = resumen.querySelector("[data-resumen-fecha]");
    const hora = resumen.querySelector("[data-resumen-hora]");
    // El día que se está mirando, tal como lo escribió el servidor: el resumen
    // no lo recalcula, solo lo repite al lado de la hora elegida.
    const dia = fecha.textContent.trim();

    document.querySelectorAll(".slot__radio").forEach((radio) => {
        radio.addEventListener("change", () => {
            if (!radio.checked) return;
            resumen.classList.add("resumen-turno--elegido");
            fecha.textContent = dia;
            hora.textContent = `De ${radio.value} a ${radio.dataset.hasta}`;
        });
    });
});


// Los <select> de filtro que se envían solos al cambiar.
//
// Antes cada uno traía onchange="this.form.submit()" escrito en el HTML. Eso
// es un atributo inline, y la CSP (ver services/seguridad.py) no lo puede
// permitir sin 'unsafe-inline' en script-src, que es justamente lo que dejaría
// a la política sin valor contra XSS. Un nonce tampoco alcanza: los nonces
// habilitan etiquetas <script>, no atributos onXXX.
//
// Delegado en document y no un listener por <select>: los cuatro que hay hoy
// viven en tres pantallas distintas, y el que se agregue mañana funciona con
// sólo escribirle data-autoenviar.
//
// Sin JavaScript queda exactamente como quedaba antes, ni mejor ni peor: el
// onchange también necesitaba JS. Los filtros de favoritos igual se pueden
// aplicar con su botón; los de radio y orden del catálogo dependen de esto,
// como dependían del atributo.
document.addEventListener("change", (evento) => {
    const control = evento.target.closest("[data-autoenviar]");
    if (control && control.form) {
        control.form.submit();
    }
});
