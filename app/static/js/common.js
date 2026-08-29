async function apiPost(url, data = {}) {

    try {

        const response = await fetch(
            url,
            {
                method: "POST",

                headers: {
                    "Content-Type": "application/json"
                },

                body: JSON.stringify(data)
            }
        );


        const result = await response.json();

        return result;

    } catch (error) {

        console.error(
            "API request failed:",
            error
        );


        return {
            ok: false,
            error: String(error)
        };

    }
}


/* ==========================================================
   Utility Window Manager
   ========================================================== */

const utilityWindows = {};

function openUtilityWindow(url, name, width = 900, height = 700) {

    const left = Math.max(
        0,
        Math.round(
            window.screenX +
            (window.outerWidth - width) / 2
        )
    );

    const top = Math.max(
        0,
        Math.round(
            window.screenY +
            (window.outerHeight - height) / 2
        )
    );

    const features = [
        `width=${width}`,
        `height=${height}`,
        `left=${left}`,
        `top=${top}`,
        "resizable=yes",
        "scrollbars=yes"
    ].join(",");

    let utilityWindow = utilityWindows[name];

    if (
        utilityWindow &&
        !utilityWindow.closed
    ) {
        utilityWindow.focus();
        return utilityWindow;
    }

    utilityWindow = window.open(
        url,
        `smart_bowl_${name}`,
        features
    );

    utilityWindows[name] = utilityWindow;

    if (utilityWindow) {
        utilityWindow.focus();
    }

    return utilityWindow;
}
