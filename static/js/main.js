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

        // Por ahora no tenés categoría ni ubicación en el modelo,
        // así que usamos textos genéricos. Cuando agregues campos,
        // simplemente los reemplazamos acá.
        const categoryText = "Emprendimiento local";
        const locationText = "Ubicación no especificada";

        card.innerHTML = `
            <div class="card__body">
                <div class="card__tags">
                    <span class="badge badge--category">${categoryText}</span>
                </div>
                <h3 class="card__title">${title}</h3>
                <p class="card__location">${locationText}</p>
                <p class="card__description">${shortBody}</p>
            </div>
        `;

        grid.appendChild(card);
    });
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
                <div class="card__tags">
                    <span class="badge badge--category">${categoryText}</span>
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
function applySearchFilter() {
    const input = document.getElementById("search-text");
    if (!input) return ALL_POSTS;

    const query = input.value.trim().toLowerCase();

    if (!query) {
        return ALL_POSTS;
    }

    return ALL_POSTS.filter((post) => {
        const title = (post.title || "").toLowerCase();
        const body = (post.body || "").toLowerCase();
        return title.includes(query) || body.includes(query);
    });
}

document.addEventListener("DOMContentLoaded", () => {
    const grid = document.getElementById("posts-grid");
    const errorEl = document.getElementById("posts-error");
    const searchForm = document.getElementById("search-form");

    if (!grid) return; // no estamos en la home

    // Cargar posts desde la API
    fetch("/api/posts/")
        .then((res) => {
            if (!res.ok) {
                throw new Error("Error al obtener los posts");
            }
            return res.json();
        })
        .then((data) => {
            ALL_POSTS = Array.isArray(data) ? data : [];
            renderPosts(ALL_POSTS);
        })
        .catch((err) => {
            console.error(err);
            if (errorEl) errorEl.style.display = "block";
        });

    // Manejar búsqueda
    if (searchForm) {
        searchForm.addEventListener("submit", (e) => {
            e.preventDefault();
            const filtered = applySearchFilter();
            renderPosts(filtered);
        });

        // Opcional: filtro en tiempo real
        const input = document.getElementById("search-text");
        if (input) {
            input.addEventListener("input", () => {
                const filtered = applySearchFilter();
                renderPosts(filtered);
            });
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
            userMenu.classList.toggle("user-menu--open");
        });

        // Cerrar menú al hacer click fuera
        document.addEventListener("click", () => {
            userMenu.classList.remove("user-menu--open");
        });
    }

    // --- LÓGICA MENÚ MÓVIL (NUEVO) ---
    const mobileToggle = document.querySelector(".navbar__toggle");
    const navbar = document.querySelector(".navbar"); // El contenedor principal

    if (mobileToggle && navbar) {
        mobileToggle.addEventListener("click", (event) => {
            event.stopPropagation();
            // Añade/quita la clase .navbar--mobile-open al <header class="navbar">
            navbar.classList.toggle("navbar--mobile-open");
        });
    }

    // Opcional: Cerrar menú móvil si se hace clic fuera de él (en 'main' o 'footer')
    const mainContent = document.querySelector("main");
    if (mainContent && navbar) {
        mainContent.addEventListener("click", () => {
            navbar.classList.remove("navbar--mobile-open");
        });
    }

});
// Mapa 
document.addEventListener("DOMContentLoaded", () => {
    const mapContainer = document.getElementById("map");
    if (!mapContainer) return; // si no hay mapa en esta página, salir

    const map = new maplibregl.Map({
        container: 'map',
        style: `https://api.maptiler.com/maps/streets/style.json?key={{ MAPTILER_KEY }}`,
        center: [-68.8458, -32.8895], // Mendoza, Argentina
        zoom: 12
    });

    map.addControl(new maplibregl.NavigationControl());

    new maplibregl.Marker({ color: "#007bff" })
        .setLngLat([-68.8458, -32.8895])
        .setPopup(new maplibregl.Popup().setText("Mendoza, Argentina"))
        .addTo(map);
});