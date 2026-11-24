/** @odoo-module **/

import { Component, onMounted, onWillUnmount, useState } from "@odoo/owl";
import { useBus, useService } from "@web/core/utils/hooks";

const STORAGE_KEY = "conagra_sidebar_collapsed";

function normalizeText(value) {
    return (value || "")
        .toLowerCase()
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "");
}

export class ConagraSidebar extends Component {
    static template = "conagra_backend_theme.ConagraSidebar";
    static props = {};

    setup() {
        this.menuService = useService("menu");
        this.state = useState({
            collapsed: window.localStorage.getItem(STORAGE_KEY) === "1",
            search: "",
        });

        useBus(this.env.bus, "MENUS:APP-CHANGED", () => {
            this.render();
        });

        onMounted(() => {
            document.body.classList.add("o_conagra_has_sidebar");
            document.body.classList.toggle("o_conagra_sidebar_collapsed", this.state.collapsed);
            window.dispatchEvent(new Event("resize"));
        });

        onWillUnmount(() => {
            document.body.classList.remove("o_conagra_has_sidebar", "o_conagra_sidebar_collapsed");
            window.dispatchEvent(new Event("resize"));
        });
    }

    get apps() {
        const allApps = this.menuService.getApps() || [];
        const query = normalizeText(this.state.search.trim());
        if (!query) {
            return allApps;
        }
        return allApps.filter((app) => normalizeText(app.name).includes(query));
    }

    get currentAppId() {
        return this.menuService.getCurrentApp()?.id || null;
    }

    getMenuItemHref(app) {
        if (!app) {
            return "/odoo";
        }
        return `/odoo/${app.actionPath || "action-" + app.actionID}`;
    }

    getAppInitials(name) {
        const words = (name || "CG").trim().split(/\s+/);
        if (words.length >= 2) {
            return (words[0][0] + words[1][0]).toUpperCase();
        }
        return words[0].slice(0, 2).toUpperCase();
    }

    toggleCollapse() {
        this.state.collapsed = !this.state.collapsed;
        if (this.state.collapsed) {
            this.state.search = "";
        }
        window.localStorage.setItem(STORAGE_KEY, this.state.collapsed ? "1" : "0");
        document.body.classList.toggle("o_conagra_sidebar_collapsed", this.state.collapsed);
        window.setTimeout(() => {
            window.dispatchEvent(new Event("resize"));
        }, 220);
    }

    async selectApp(app) {
        if (!app) {
            return;
        }
        this.state.search = "";
        await this.menuService.selectMenu(app);
    }

    clearSearch() {
        this.state.search = "";
    }

    onSearchKeydown(ev) {
        if (ev.key === "Enter" && this.apps.length) {
            ev.preventDefault();
            this.selectApp(this.apps[0]);
        } else if (ev.key === "Escape") {
            this.state.search = "";
        }
    }
}
