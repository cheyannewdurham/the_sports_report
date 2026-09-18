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

// Live player enrichment

const playerLiveProfile = document.querySelector(".player-live-profile[data-live-url]");

function setLiveText(key, value) {
    document.querySelectorAll(`[data-live-field="${key}"]`).forEach((element) => {
        element.textContent = value || "";
    });
}

function setLiveRow(key, value) {
    document.querySelectorAll(`[data-live-row="${key}"]`).forEach((element) => {
        element.hidden = !value;
    });
}

function joinLiveParts(parts) {
    return parts.filter(Boolean).join(" · ");
}

if (playerLiveProfile) {
    fetch(playerLiveProfile.dataset.liveUrl, {
        headers: {
            "Accept": "application/json"
        }
    })
        .then((response) => (response.ok ? response.json() : null))
        .then((data) => {
            if (!data) {
                return;
            }

            const currentTeam = data.display_current_team || "";
            const heightWeight = joinLiveParts([
                data.height || "",
                data.weight ? `${data.weight} lbs` : ""
            ]);
            const draft = data.draft_year
                ? [
                    data.draft_year,
                    data.draft_round ? `Round ${data.draft_round}` : "",
                    data.draft_number ? `Pick ${data.draft_number}` : ""
                ].filter(Boolean).join(", ")
                : "";
            const countryCollege = joinLiveParts([data.country || "", data.college || ""]);
            const born = joinLiveParts([data.birth_date || "", data.birth_place || ""]);

            setLiveText("display_current_team", currentTeam);
            setLiveText("position", data.position || "");
            setLiveText("height_weight", heightWeight);
            setLiveText("draft", draft);
            setLiveText("country_college", countryCollege);
            setLiveText("born", born);

            setLiveRow("display_current_team", currentTeam);
            setLiveRow("position", data.position);
            setLiveRow("height_weight", heightWeight);
            setLiveRow("draft", draft);
            setLiveRow("country_college", countryCollege);
            setLiveRow("born", born);

            if (data.image) {
                const imageFrame = document.querySelector(".player-image-frame");
                const existingImage = document.querySelector("[data-live-image]");
                const placeholder = document.querySelector("[data-live-image-placeholder]");

                if (existingImage) {
                    existingImage.src = data.image;
                } else if (imageFrame) {
                    const image = document.createElement("img");
                    image.src = data.image;
                    image.alt = data.name || "";
                    image.dataset.liveImage = "";
                    imageFrame.appendChild(image);
                }

                if (placeholder) {
                    placeholder.remove();
                }
            }

            const statLine = data.stat_line || {};
            const statLineElement = document.querySelector("[data-live-stat-line]");

            if (statLineElement && Object.keys(statLine).length > 0) {
                statLineElement.hidden = false;
                setLiveText("stat_season_label", statLine.season_label ? `${statLine.season_label} regular season` : "");

                [
                    "points",
                    "rebounds",
                    "assists",
                    "steals",
                    "blocks",
                    "minutes",
                    "games_played"
                ].forEach((key) => {
                    const value = statLine[key] || "";
                    const stat = document.querySelector(`[data-live-stat="${key}"]`);

                    if (stat) {
                        stat.hidden = !value;
                    }

                    setLiveText(`stat_${key}`, value);
                });
            }
        })
        .catch(() => {});
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
