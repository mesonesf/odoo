/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { WebClient } from "@web/webclient/webclient";
import { ConagraSidebar } from "./sidebar/conagra_sidebar";

patch(WebClient, {
    components: {
        ...WebClient.components,
        ConagraSidebar,
    },
});

patch(WebClient.prototype, {
    setup() {
        super.setup(...arguments);
        this.title.setParts({ zopenerp: "CONAGRA ERP" });
    },
});
