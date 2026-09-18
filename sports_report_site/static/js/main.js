// Reveal sections when they scroll into view

const animatedElements = document.querySelectorAll(".animate-on-scroll");

if ("IntersectionObserver" in window) {
    const observer = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
            if (entry.isIntersecting) {
                entry.target.classList.add("is-visible");
            }
        });
    }, {
        threshold: 0.18
    });

    animatedElements.forEach((element) => {
        observer.observe(element);
    });
} else {
    animatedElements.forEach((element) => {
        element.classList.add("is-visible");
    });
}

// Player database search

const playerSearch = document.querySelector(".player-search");
const searchablePlayers = document.querySelectorAll(".searchable-player");

if (playerSearch && searchablePlayers.length > 0) {
    playerSearch.addEventListener("input", () => {
        const query = playerSearch.value.trim().toLowerCase();

        searchablePlayers.forEach((playerCard) => {
            const content = playerCard.dataset.search.toLowerCase();
            playerCard.hidden = query && !content.includes(query);
        });
    });
}

// League database typeahead

const databaseSearch = document.querySelector(".database-search-input");
const databaseSearchResults = document.querySelector(".database-search-results");

function normalizeSearchText(value) {
    return value.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
}

function escapeHtml(value) {
    return value.replace(/[&<>"']/g, (character) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        "\"": "&quot;",
        "'": "&#039;"
    }[character]));
}

function scoreDatabaseResult(item, query) {
    const name = normalizeSearchText(item.name || "");

    if (name.includes(query)) {
        return item.type === "team" ? 0 : 1;
    }

    return 2;
}

if (databaseSearch && databaseSearchResults) {
    let searchIndex = [];

    try {
        searchIndex = JSON.parse(databaseSearch.dataset.searchIndex || "[]");
    } catch (error) {
        searchIndex = [];
    }

    function renderSearchResults() {
        const query = normalizeSearchText(databaseSearch.value);

        if (!query) {
            databaseSearchResults.hidden = true;
            databaseSearchResults.innerHTML = "";
            databaseSearch.setAttribute("aria-expanded", "false");
            return;
        }

        const results = searchIndex
            .filter((item) => normalizeSearchText(item.search || "").includes(query))
            .sort((left, right) => (
                scoreDatabaseResult(left, query) - scoreDatabaseResult(right, query)
                || (left.name || "").localeCompare(right.name || "")
            ))
            .slice(0, 10);

        if (results.length === 0) {
            databaseSearchResults.hidden = false;
            databaseSearchResults.innerHTML = '<div class="database-search-empty">No matches found</div>';
            databaseSearch.setAttribute("aria-expanded", "true");
            return;
        }

        databaseSearchResults.hidden = false;
        databaseSearchResults.innerHTML = results.map((item) => {
            const label = item.type === "team" ? "Team" : "Player";
            const players = (item.players || []).slice(0, 6);
            const extraCount = Math.max((item.players || []).length - players.length, 0);
            const playerList = item.type === "team"
                ? `<p>${players.map(escapeHtml).join(", ")}${extraCount ? `, +${extraCount} more` : ""}</p>`
                : "";
            const content = `
                <span>${escapeHtml(label)}</span>
                <strong>${escapeHtml(item.name)}</strong>
                <small>${escapeHtml(item.team || "")}</small>
                ${playerList}
            `;

            if (item.url) {
                return `<a class="database-search-result" href="${escapeHtml(item.url)}" role="option">${content}</a>`;
            }

            return `<button class="database-search-result" type="button" role="option" data-fill="${escapeHtml(item.name)}">${content}</button>`;
        }).join("");
        databaseSearch.setAttribute("aria-expanded", "true");
    }

    databaseSearch.addEventListener("input", renderSearchResults);

    databaseSearchResults.addEventListener("click", (event) => {
        const button = event.target.closest("button[data-fill]");

        if (!button) {
            return;
        }

        databaseSearch.value = button.dataset.fill;
        renderSearchResults();
    });

    document.addEventListener("click", (event) => {
        if (
            event.target === databaseSearch
            || databaseSearchResults.contains(event.target)
        ) {
            return;
        }

        databaseSearchResults.hidden = true;
        databaseSearch.setAttribute("aria-expanded", "false");
    });

    databaseSearch.addEventListener("focus", renderSearchResults);
}


// Mouse-position auto-scroll for latest uploads carousel

const carouselWrapper = document.querySelector(".video-carousel-wrapper");
const carousel = document.querySelector(".video-carousel");

if (carouselWrapper && carousel) {
    let scrollDirection = 0;

    carouselWrapper.addEventListener("mousemove", (event) => {
        const bounds = carouselWrapper.getBoundingClientRect();
        const x = event.clientX - bounds.left;

        const edgeSize = bounds.width * 0.25;

        if (x < edgeSize) {
            scrollDirection = -1;
        } else if (x > bounds.width - edgeSize) {
            scrollDirection = 1;
        } else {
            scrollDirection = 0;
        }
    });

    carouselWrapper.addEventListener("mouseleave", () => {
        scrollDirection = 0;
    });

    function autoScrollCarousel() {
        if (scrollDirection !== 0) {
            carousel.scrollLeft += scrollDirection * 6;
        }

        requestAnimationFrame(autoScrollCarousel);
    }

    autoScrollCarousel();
}
