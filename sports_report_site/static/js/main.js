// Reveal sections when they scroll into view

const animatedElements = document.querySelectorAll(".animate-on-scroll");

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