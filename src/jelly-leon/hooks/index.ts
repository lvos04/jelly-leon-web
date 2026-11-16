/**
 * Jelly Leon: de fork-eigen haakmodule van de webclient (bouwplan B03 §10.11, ADR-0001 trede 4).
 *
 * Elke haak in een upstream-bestand wordt later precies één regel `jlHook('naam', ctx)` (of één render-slot
 * `<JlHookSlot name='naam' ctx={ctx} />`, zie `JlHookSlot.tsx`), met een eigen regel `JLW-NNNN` in
 * `docs/platform-v2/PATCHES.md`. De handler zelf staat in fork-eigen code en wordt pas bij de eerste aanroep met een
 * dynamische `import()` geladen.
 *
 * Een fout in fork-code mag het upstream-scherm nooit breken: een onbekende naam, een ontbrekende handler, een
 * mislukte import of een fout in de handler laten `jlHook` gewoon terugkeren (de belofte wordt nooit afgewezen).
 * Er komt dan hooguit één regel op de console met de naam van de haak en het soort fout, nooit de context, de
 * foutmelding of andere gegevens van de gebruiker.
 *
 * Regel voor elke upstream-haak: een upstream-plek awaitet `jlHook` nooit in een pad dat het scherm tekent. Daar is
 * de aanroep fire-and-forget: `void jlHook('naam', ctx);` (`void` voor de lintregel no-floating-promises). Er is
 * bewust geen time-out: de belofte rondt pas af als de handler afrondt, dus een handler die nooit afrondt laat alleen
 * een aanroeper hangen die wacht; een aanroeper die niet wacht, gaat gewoon door.
 */

/** De gegevens die de upstream-plek aan de haak meegeeft. */
export type JlHookContext = Readonly<Record<string, unknown>>;

/** Een handler voor `jlHook`: krijgt de context en mag een waarde (of een belofte) teruggeven. */
export type JlHookHandler = (ctx: JlHookContext) => unknown;

/**
 * Wat een dynamische `import()` van een handlermodule oplevert. De standaardexport is voor `jlHook` een
 * {@link JlHookHandler} en voor `JlHookSlot` een React-onderdeel met de prop `ctx`. Het type is bewust ruim:
 * de module controleert de export zelf, zodat een verkeerde export nooit de aanroeper breekt.
 */
export interface JlHookModule {
    default?: unknown;
}

/** Laadt een handlermodule, altijd als `() => import('../<pad>')`. */
export type JlHookLoader = () => Promise<JlHookModule>;

/** Eén regel in de tabel met handlers: `[haaknaam, lader]`. */
export type JlHookEntry = readonly [string, JlHookLoader];

/**
 * De tabel met handlers: een lijst van `[haaknaam, lader]`. Bewust een lijst en geen object: zo kunnen haaknamen met
 * een punt (zoals 'syncplay.menu') zonder lintuitzondering (de regel naming-convention keurt zulke objectsleutels af)
 * en speelt de prototypeketen van een object geen rol. Staat een naam er twee keer in, dan telt de eerste regel.
 */
export type JlHookTable = readonly JlHookEntry[];

/**
 * De tabel met handlers. In deze stap leeg: er is nog geen haak geplaatst. Een handler komt hier pas bij samen met
 * de haak in het upstream-bestand (eigen regel `JLW-NNNN` in het patchregister), bijvoorbeeld
 * `['syncplay.menu', () => import('../features/<functie>/menu')]`.
 */
export const JL_HOOK_HANDLERS: JlHookTable = [];

const LOG_PREFIX = '[Jelly Leon] haak';

/**
 * Het soort fout, zonder de foutmelding zelf (die kan gebruikersgegevens bevatten). Gooit nooit: faalt het uitlezen
 * van de fout zelf (een gooiende getter op `name`, een ingetrokken Proxy waarop `instanceof` faalt), dan 'onbekend'.
 */
export function jlHookErrorKind(error: unknown): string {
    try {
        if (error instanceof Error && typeof error.name === 'string' && /^[A-Za-z]{1,40}$/.test(error.name)) {
            return error.name;
        }
        return typeof error;
    } catch {
        return 'onbekend';
    }
}

/**
 * Schrijft één consoleregel. Alleen de haaknaam (uit de code van de aanroeper) en een vaste reden; nooit de context
 * of een foutmelding. Faalt de console zelf, dan gebeurt er niets.
 */
export function logJlHookProblem(name: string, reason: string): void {
    try {
        console.warn(`${LOG_PREFIX} "${String(name).slice(0, 80)}": ${reason}`);
    } catch {
        // De console mag de aanroeper ook niet breken.
    }
}

/** Zoekt de lader op: de eerste regel met precies deze naam. Een kapotte regel of tabel geeft `undefined`. */
function findLoader(table: JlHookTable, name: string): JlHookLoader | undefined {
    if (!Array.isArray(table)) {
        return undefined;
    }
    for (const entry of table) {
        if (Array.isArray(entry) && entry[0] === name) {
            const loader: unknown = entry[1];
            return typeof loader === 'function' ? loader as JlHookLoader : undefined;
        }
    }
    return undefined;
}

/** Welke standaardexport een aanroeper accepteert, met de vaste reden voor de consoleregel als die niet klopt. */
export interface JlHookExportCheck {
    accepts: (value: unknown) => boolean;
    reason: string;
}

/** Voor `jlHook`: de standaardexport moet een functie zijn. */
export const JL_HOOK_HANDLER_CHECK: JlHookExportCheck = {
    accepts: value => typeof value === 'function',
    reason: 'module heeft geen handler (standaardexport is geen functie)'
};

/**
 * Laadt de standaardexport van de handlermodule voor `name`. Geeft `undefined` (en schrijft één consoleregel) bij
 * een onbekende naam, een kapotte tabelregel, een mislukte import of een export die `check` niet accepteert (voor
 * `jlHook`: geen functie). Wordt nooit afgewezen.
 */
export async function loadJlHookExport(
    table: JlHookTable,
    name: string,
    check: JlHookExportCheck = JL_HOOK_HANDLER_CHECK
): Promise<unknown> {
    let loader: JlHookLoader | undefined;
    try {
        loader = findLoader(table, name);
    } catch {
        loader = undefined;
    }
    if (!loader) {
        logJlHookProblem(name, 'onbekende naam of geen handler in de tabel');
        return undefined;
    }

    let module: JlHookModule | undefined;
    try {
        module = await loader();
    } catch (error) {
        logJlHookProblem(name, `laden mislukt (${jlHookErrorKind(error)})`);
        return undefined;
    }

    let handler: unknown;
    let accepted: boolean;
    try {
        handler = module?.default;
        accepted = check.accepts(handler);
    } catch {
        accepted = false;
    }
    if (!accepted) {
        logJlHookProblem(name, check.reason);
        return undefined;
    }
    return handler;
}

/**
 * Maakt een `jlHook` bij een tabel. De fabriek bestaat voor de tests; de webclient gebruikt alleen {@link jlHook}.
 */
export function createJlHook(table: JlHookTable) {
    return async function hook(name: string, ctx: JlHookContext = {}): Promise<unknown> {
        try {
            const handler = await loadJlHookExport(table, name);
            if (handler === undefined) {
                return undefined;
            }
            return await (handler as JlHookHandler)(ctx);
        } catch (error) {
            logJlHookProblem(name, `handler gaf een fout (${jlHookErrorKind(error)})`);
            return undefined;
        }
    };
}

/**
 * Roept de fork-eigen handler voor `name` aan met `ctx`. Keert altijd terug: met de uitkomst van de handler, of met
 * `undefined` als er iets misgaat. Zolang geen upstream-bestand deze module importeert, zit zij niet in de bundel.
 */
export const jlHook = createJlHook(JL_HOOK_HANDLERS);
