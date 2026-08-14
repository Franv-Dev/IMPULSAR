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
        const shortBody =
            body.length > 150 ? body.slice(0, 150) + "..." : body;

        // --- INICIO DE CAMBIOS ---
        
        // 1. Construimos las URLs que necesitamos
        const postDetailUrl = `/blog/${post.id}`; // URL a la vista de detalle
        const postAbsoluteUrl = `${location.origin}${postDetailUrl}`; // para compartir
        const postImageUrl = post.image ? `/static/uploads/${escapeHtml(post.image)}` : null;

        // 2. Variable para el HTML de la imagen (si existe)
        let imageHtml = "";
        if (postImageUrl) {
            imageHtml = `
            <a href="${postDetailUrl}" class="card__image-link">
                <div class="card__image-wrapper">
                    <img src="${postImageUrl}" alt="Imagen de ${title}" class="card__image">
                </div>
            </a>
            `;
        }

        // 3. Textos genéricos (como ya tenías)
        const categoryText = "Emprendimiento local";
        const locationText = "Ubicación no especificada";

        // 4. Actualizamos el innerHTML para incluir la imagen
        //    y los links en el título y el botón.
        card.innerHTML = `
            ${imageHtml} 
            <div class="card__body">
                <div class="card__tags" style="display:flex; justify-content:space-between; align-items:flex-start;">
                    <span class="badge badge--category">${categoryText}</span>
                    <button type="button" class="share-btn"
                        data-share-url="${postAbsoluteUrl}"
                        data-share-title="${title}"
                        aria-label="Compartir ${title}"
                        title="Compartir">
                        🔗
                    </button>
                </div>
                <h3 class="card__title">
                    <a href="${postDetailUrl}" style="text-decoration:none; color:inherit;">
                        ${title}
                    </a>
                </h3>
                <p class="card__location">${locationText}</p>
                <p class="card__description">${shortBody}</p>
                <div style="margin-top:0.75rem; text-align:right;">
                    <a href="${postDetailUrl}" class="btn btn--secondary" style="font-size:0.8rem; padding:0.3rem 0.8rem;">
                        Ver detalle / Reseñas
                    </a>
                </div>
            </div>
        `;
        // --- FIN DE CAMBIOS ---

        grid.appendChild(card);
    });
}
// Pide los emprendimientos al servidor. La busqueda se resuelve en la base de
// datos y no en el navegador: antes se descargaban TODOS los posts y se
// filtraban aca, lo que deja de funcionar apenas la plataforma crezca.
function fetchPosts(query) {
    const params = new URLSearchParams();
    if (query) params.set("q", query);
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

    if (!grid) return; // no estamos en la home

    function cargar(query) {
        // En conexiones lentas la grilla queda vacia varios segundos sin este
        // aviso, y parece que la pagina no respondio.
        if (errorEl) errorEl.style.display = "none";
        if (loadingEl) loadingEl.style.display = "block";
        grid.innerHTML = "";

        fetchPosts(query)
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

    cargar("");

    if (searchForm) {
        searchForm.addEventListener("submit", (e) => {
            e.preventDefault();
            cargar(input ? input.value.trim() : "");
        });

        if (input) {
            input.addEventListener(
                "input",
                debounce(() => cargar(input.value.trim()), 300)
            );
        }
    }
});
// =============================
// MENÚ DE USUARIO EN LA NAVBAR
// =============================
document.addEventListener("DOMContentLoaded", () => {
    
    // --- LÓGICA MENÚ DE USUARIO (la que ya tenías) ---
    const userToggle = document.querySelector(".navbar__user-toggle");
    const userMenu = document.getElementById("user-menu");

    if (userToggle && userMenu) {
        // Abrir/cerrar menú al hacer click en el usuario
        userToggle.addEventListener("click", (event) => {
            event.stopPropagation();
            const abierto = userMenu.classList.toggle("user-menu--open");
            userToggle.setAttribute("aria-expanded", abierto ? "true" : "false");
        });

        // Cerrar menú al hacer click fuera
        document.addEventListener("click", () => {
            userMenu.classList.remove("user-menu--open");
            userToggle.setAttribute("aria-expanded", "false");
        });
    }

    // --- LÓGICA MENÚ MÓVIL (NUEVO) ---
    const mobileToggle = document.querySelector(".navbar__toggle");
    const navbar = document.querySelector(".navbar"); // El contenedor principal

    if (mobileToggle && navbar) {
        mobileToggle.addEventListener("click", (event) => {
            event.stopPropagation();
            // Añade/quita la clase .navbar--mobile-open al <header class="navbar">
            const abierto = navbar.classList.toggle("navbar--mobile-open");
            mobileToggle.setAttribute("aria-expanded", abierto ? "true" : "false");
        });
    }

    // Opcional: Cerrar menú móvil si se hace clic fuera de él (en 'main' o 'footer')
    const mainContent = document.querySelector("main");
    if (mainContent && navbar) {
        mainContent.addEventListener("click", () => {
            navbar.classList.remove("navbar--mobile-open");
            if (mobileToggle) mobileToggle.setAttribute("aria-expanded", "false");
        });
    }

});

// =============================
// BADGE DE NOTIFICACIONES (mensajes sin leer + reseñas sin responder)
// =============================
document.addEventListener("DOMContentLoaded", () => {
    const badge = document.getElementById("notif-badge");
    if (!badge) return; // no esta logueado, no existe el link de Mensajes

    function actualizarBadge() {
        fetch("/mensajes/notificaciones")
            .then((res) => (res.ok ? res.json() : Promise.reject(res)))
            .then((data) => {
                const total = data.total || 0;
                if (total > 0) {
                    badge.textContent = total > 9 ? "9+" : String(total);
                    badge.style.display = "inline-block";
                } else {
                    badge.style.display = "none";
                }
            })
            .catch(() => {
                // Un polling fallido no debe romper la navegacion normal.
            });
    }

    actualizarBadge();
    setInterval(actualizarBadge, 20000);
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
                boton.closest("form").submit();
            },
            () => {
                alert("No pudimos acceder a tu ubicación.");
                boton.disabled = false;
                boton.textContent = textoOriginal;
            }
        );
    });
});