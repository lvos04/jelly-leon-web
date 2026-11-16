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

/** De tabel met handlers: haaknaam -> lader. */
export type JlHookTable = Readonly<Record<string, JlHookLoader>>;

/**
 * De tabel met handlers. In deze stap leeg: er is nog geen haak geplaatst. Een handler komt hier pas bij samen met
 * de haak in het upstream-bestand (eigen regel `JLW-NNNN` in het patchregister), bijvoorbeeld
 * `'naam': () => import('../features/<functie>/naam')`.
 */
export const JL_HOOK_HANDLERS: JlHookTable = {};

const LOG_PREFIX = '[Jelly Leon] haak';

/** Het soort fout, zonder de foutmelding zelf (die kan gebruikersgegevens bevatten). */
export function jlHookErrorKind(error: unknown): string {
    if (error instanceof Error && typeof error.name === 'string' && /^[A-Za-z]{1,40}$/.test(error.name)) {
        return error.name;
    }
    return typeof error;
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

/** Zoekt de lader op; alleen eigen sleutels van de tabel tellen (geen `constructor`, `__proto__` en dergelijke). */
function findLoader(table: JlHookTable, name: string): JlHookLoader | undefined {
    if (!Object.prototype.hasOwnProperty.call(table, name)) {
        return undefined;
    }
    const loader: unknown = table[name];
    return typeof loader === 'function' ? loader as JlHookLoader : undefined;
}

/**
 * Laadt de standaardexport van de handlermodule voor `name`. Geeft `undefined` (en schrijft één consoleregel) bij
 * een onbekende naam, een kapotte tabelregel, een mislukte import of een export die geen functie is. Wordt nooit
 * afgewezen.
 */
export async function loadJlHookExport(table: JlHookTable, name: string): Promise<unknown> {
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
    try {
        handler = module?.default;
    } catch {
        handler = undefined;
    }
    if (typeof handler !== 'function') {
        logJlHookProblem(name, 'module heeft geen handler (standaardexport is geen functie)');
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
