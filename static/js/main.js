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
});