/** @odoo-module **/

import { Component, onMounted, onWillUnmount, useState } from "@odoo/owl";
import { useBus, useService } from "@web/core/utils/hooks";

const STORAGE_KEY = "conagra_sidebar_collapsed";

// Orden solicitado de aplicaciones raíz (xmlid exactos de Odoo 18)
const APP_ORDER_BY_XMLID = {
    "spreadsheet_dashboard.spreadsheet_dashboard_menu_root": 10, // Tableros
    "board.menu_board_root": 11,
    "stock.menu_stock_root": 20, // Inventario
    "crm.crm_menu_root": 30, // CRM
    "sale.sale_menu_root": 40, // Ventas
    "sale_management.sale_menu_root": 41,
    "purchase.menu_purchase_root": 50, // Compras
    "mrp.menu_mrp_root": 60, // Manufactura
    "account.menu_finance": 70, // Facturación
    "fleet.menu_root": 80, // Flota
    "contacts.menu_contacts": 90, // Contactos
    "hr.menu_hr_root": 100, // Empleados
    "hr_attendance.menu_hr_attendance_root": 110, // Asistencia
    "calendar.mail_menu_calendar": 120, // Calendario
    "mail.menu_root_discuss": 130, // Conversaciones
    "website.menu_website_configuration": 140, // Sitio Web
    "event.event_main_menu": 150, // Eventos
    "utm.menu_link_tracker_root": 160, // Rastreador de Enlaces
    "queue_job.menu_queue_job_root": 170, // Cola de Tarea
    "base.menu_administration": 9000, // Ajustes
    "base.menu_management": 9010, // Aplicaciones
};

// Respaldo por nombre normalizado (por idioma o traducción activa)
const APP_ORDER_BY_NAME = {
    tableros: 10,
    dashboards: 10,
    inventario: 20,
    inventory: 20,
    crm: 30,
    ventas: 40,
    sales: 40,
    compras: 50,
    purchase: 50,
    manufactura: 60,
    fabricacion: 60,
    manufacturing: 60,
    facturacion: 70,
    contabilidad: 70,
    invoicing: 70,
    accounting: 70,
    flota: 80,
    fleet: 80,
    contacto: 90,
    contactos: 90,
    contacts: 90,
    empleados: 100,
    employees: 100,
    asistencia: 110,
    asistencias: 110,
    attendances: 110,
    calendario: 120,
    calendar: 120,
    conversaciones: 130,
    debates: 130,
    discuss: 130,
    "sitio web": 140,
    website: 140,
    eventos: 150,
    events: 150,
    "rastreador de enlaces": 160,
    "link tracker": 160,
    "cola de tarea": 170,
    "cola de tareas": 170,
    "cola de trabajos": 170,
    "job queue": 170,
    ajustes: 9000,
    configuracion: 9000,
    settings: 9000,
    aplicaciones: 9010,
    apps: 9010,
};

function normalizeText(value) {
    return (value || "")
        .toLowerCase()
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "");
}

function getAppOrder(app, fallbackIndex) {
    if (app?.xmlid && app.xmlid in APP_ORDER_BY_XMLID) {
        return APP_ORDER_BY_XMLID[app.xmlid];
    }
    const normalizedName = normalizeText(app?.name).trim();
    if (normalizedName && normalizedName in APP_ORDER_BY_NAME) {
        return APP_ORDER_BY_NAME[normalizedName];
    }
    return 5000 + fallbackIndex;
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
        const orderedApps = (this.menuService.getApps() || [])
            .map((app, index) => ({ app, order: getAppOrder(app, index), index }))
            .sort((a, b) => a.order - b.order || a.index - b.index)
            .map((entry) => entry.app);

        const query = normalizeText(this.state.search.trim());
        if (!query) {
            return orderedApps;
        }
        return orderedApps.filter((app) => normalizeText(app.name).includes(query));
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
