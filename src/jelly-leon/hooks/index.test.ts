import { describe, expect, it, vi } from 'vitest';
import { createJlHook, jlHook, jlHookErrorKind, JL_HOOK_HANDLERS, type JlHookTable } from './index';

const GEHEIM = 'gebruiker-geheim-1234';

/** De vaste redenen in de consoleregel: zo is te zien welke controle de aanroep tegenhield. */
const ONBEKENDE_NAAM = 'onbekende naam of geen handler in de tabel';
const GEEN_HANDLER = 'module heeft geen handler (standaardexport is geen functie)';

function stilConsole() {
    return vi.spyOn(console, 'warn').mockImplementation(() => { /* stil in de test */ });
}

/** Een fout waarvan het uitlezen zelf faalt: de getter van `name` gooit. */
function foutMetGooiendeNaam() {
    const fout = new Error(GEHEIM);
    Object.defineProperty(fout, 'name', {
        get() {
            throw new Error('name-getter');
        }
    });
    return fout;
}

/** Een ingetrokken Proxy: elke bewerking erop gooit, ook `instanceof`. */
function ingetrokkenProxy(): object {
    const { proxy, revoke } = Proxy.revocable({}, {});
    revoke();
    return proxy;
}

/** Alle consoleregels als tekst, om te controleren dat er geen gebruikersgegevens in staan. */
function consoleTekst(spy: ReturnType<typeof stilConsole>) {
    return spy.mock.calls.map(args => args.map(String).join(' ')).join('\n');
}

/** De consoleregels als lijst. */
function consoleRegels(spy: ReturnType<typeof stilConsole>) {
    return spy.mock.calls.map(args => args.map(String).join(' '));
}

/** De consoleregel die de module voor deze haak en deze reden schrijft. */
function regel(naam: string, reden: string) {
    return `[Jelly Leon] haak "${naam}": ${reden}`;
}

describe('Jelly Leon: haakmodule (jlHook)', () => {
    describe('Tabel', () => {
        it('should have an empty handler table (no hook is placed yet)', () => {
            expect(JL_HOOK_HANDLERS).toEqual([]);
        });

        it('should have unique hook names in the handler table (the list form does not stop a duplicate)', () => {
            // In de lijstvorm wint stil de eerste regel; tsc houdt een dubbele naam niet tegen, deze test wel.
            const namen = JL_HOOK_HANDLERS.map(([ naam ]) => naam);

            expect(new Set(namen).size).toBe(namen.length);
        });

        it('should return without exception for any name with the real (empty) table', async () => {
            const warn = stilConsole();

            await expect(jlHook('syncplay.menu', { gebruiker: GEHEIM })).resolves.toBeUndefined();
            expect(consoleRegels(warn)).toEqual([ regel('syncplay.menu', ONBEKENDE_NAAM) ]);
            expect(consoleTekst(warn)).not.toContain(GEHEIM);
        });

        it('should find hook names with a dot (the list form needs no lint exception)', async () => {
            const menu = vi.fn(() => 'menu');
            const secties = vi.fn(() => 'secties');
            const tabel: JlHookTable = [
                [ 'syncplay.menu', () => Promise.resolve({ default: menu }) ],
                [ 'home.sections', () => Promise.resolve({ default: secties }) ]
            ];
            const hook = createJlHook(tabel);

            await expect(hook('syncplay.menu', {})).resolves.toBe('menu');
            await expect(hook('home.sections', {})).resolves.toBe('secties');
            expect(menu).toHaveBeenCalledTimes(1);
            expect(secties).toHaveBeenCalledTimes(1);
        });

        it('should use the first entry when a name occurs twice', async () => {
            const tabel: JlHookTable = [
                [ 'testDubbel', () => Promise.resolve({ default: () => 'eerste' }) ],
                [ 'testDubbel', () => Promise.resolve({ default: () => 'tweede' }) ]
            ];

            await expect(createJlHook(tabel)('testDubbel', {})).resolves.toBe('eerste');
        });
    });

    describe('Normaal pad', () => {
        it('should load the handler with a dynamic import and call it with the context', async () => {
            const handler = vi.fn(() => 'resultaat');
            const tabel: JlHookTable = [
                [ 'testHaak', () => Promise.resolve({ default: handler }) ]
            ];
            const ctx = { itemId: 'abc' };

            await expect(createJlHook(tabel)('testHaak', ctx)).resolves.toBe('resultaat');
            expect(handler).toHaveBeenCalledTimes(1);
            expect(handler).toHaveBeenCalledWith(ctx);
        });

        it('should await an async handler and return its result', async () => {
            const tabel: JlHookTable = [
                [ 'testAsync', () => Promise.resolve({ default: () => Promise.resolve(42) }) ]
            ];

            await expect(createJlHook(tabel)('testAsync', {})).resolves.toBe(42);
        });

        it('should pass an empty context when none is given', async () => {
            const handler = vi.fn();
            const tabel: JlHookTable = [ [ 'testLeeg', () => Promise.resolve({ default: handler }) ] ];

            await createJlHook(tabel)('testLeeg');

            expect(handler).toHaveBeenCalledWith({});
        });
    });

    describe('Negatief: de aanroeper breekt nooit', () => {
        it('should return without exception when the handler throws', async () => {
            const warn = stilConsole();
            const tabel: JlHookTable = [
                [ 'testGooit', () => Promise.resolve({
                    default: (ctx: Readonly<Record<string, unknown>>) => {
                        throw new Error(`kapot voor ${String(ctx.gebruiker)}`);
                    }
                }) ]
            ];

            await expect(createJlHook(tabel)('testGooit', { gebruiker: GEHEIM })).resolves.toBeUndefined();
            expect(consoleRegels(warn)).toEqual([ regel('testGooit', 'handler gaf een fout (Error)') ]);
            expect(consoleTekst(warn)).not.toContain(GEHEIM);
        });

        it('should return without exception when an async handler rejects', async () => {
            const warn = stilConsole();
            const tabel: JlHookTable = [
                [ 'testWeigert', () => Promise.resolve({
                    default: () => Promise.reject(new Error(GEHEIM))
                }) ]
            ];

            await expect(createJlHook(tabel)('testWeigert', {})).resolves.toBeUndefined();
            expect(consoleRegels(warn)).toEqual([ regel('testWeigert', 'handler gaf een fout (Error)') ]);
            expect(consoleTekst(warn)).not.toContain(GEHEIM);
        });

        it('should return without exception when the handler throws a value whose kind cannot be read', async () => {
            const warn = stilConsole();
            const tabel: JlHookTable = [
                [ 'testNaamGetter', () => Promise.resolve({
                    default: () => {
                        throw foutMetGooiendeNaam();
                    }
                }) ],
                [ 'testProxy', () => Promise.resolve({
                    default: () => Promise.reject(ingetrokkenProxy())
                }) ]
            ];
            const hook = createJlHook(tabel);

            await expect(hook('testNaamGetter', {})).resolves.toBeUndefined();
            await expect(hook('testProxy', {})).resolves.toBeUndefined();
            expect(consoleRegels(warn)).toEqual([
                regel('testNaamGetter', 'handler gaf een fout (onbekend)'),
                regel('testProxy', 'handler gaf een fout (onbekend)')
            ]);
            expect(consoleTekst(warn)).not.toContain(GEHEIM);
        });

        it('should return without exception when the import fails', async () => {
            const warn = stilConsole();
            const tabel: JlHookTable = [
                [ 'testImport', () => Promise.reject(new Error(`chunk ${GEHEIM} niet gevonden`)) ]
            ];

            await expect(createJlHook(tabel)('testImport', {})).resolves.toBeUndefined();
            expect(consoleRegels(warn)).toEqual([ regel('testImport', 'laden mislukt (Error)') ]);
            expect(consoleTekst(warn)).not.toContain(GEHEIM);
        });

        it('should return without exception when the import fails with a value whose kind cannot be read', async () => {
            const warn = stilConsole();
            const tabel: JlHookTable = [
                [ 'testImportNaam', () => Promise.reject(foutMetGooiendeNaam()) ],
                [ 'testImportProxy', () => Promise.reject(ingetrokkenProxy()) ]
            ];
            const hook = createJlHook(tabel);

            await expect(hook('testImportNaam', {})).resolves.toBeUndefined();
            await expect(hook('testImportProxy', {})).resolves.toBeUndefined();
            expect(consoleRegels(warn)).toEqual([
                regel('testImportNaam', 'laden mislukt (onbekend)'),
                regel('testImportProxy', 'laden mislukt (onbekend)')
            ]);
        });

        it('should return without exception when the loader itself throws synchronously', async () => {
            const warn = stilConsole();
            const tabel: JlHookTable = [
                [ 'testLader', () => {
                    throw new Error(GEHEIM);
                } ]
            ];

            await expect(createJlHook(tabel)('testLader', {})).resolves.toBeUndefined();
            expect(consoleRegels(warn)).toEqual([ regel('testLader', 'laden mislukt (Error)') ]);
        });

        it('should return without exception for an unknown name', async () => {
            const warn = stilConsole();
            const tabel: JlHookTable = [
                [ 'testBekend', () => Promise.resolve({ default: vi.fn() }) ]
            ];

            await expect(createJlHook(tabel)('testOnbekend', { gebruiker: GEHEIM })).resolves.toBeUndefined();
            expect(consoleRegels(warn)).toEqual([ regel('testOnbekend', ONBEKENDE_NAAM) ]);
            expect(consoleTekst(warn)).not.toContain(GEHEIM);
        });

        it('should not treat names from the object prototype as handlers', async () => {
            const warn = stilConsole();
            const hook = createJlHook([]);

            await expect(hook('constructor', {})).resolves.toBeUndefined();
            await expect(hook('toString', {})).resolves.toBeUndefined();
            await expect(hook('__proto__', {})).resolves.toBeUndefined();
            expect(consoleRegels(warn)).toEqual([
                regel('constructor', ONBEKENDE_NAAM),
                regel('toString', ONBEKENDE_NAAM),
                regel('__proto__', ONBEKENDE_NAAM)
            ]);
        });

        it('should return without exception when the module has no handler function', async () => {
            const warn = stilConsole();
            const tabel: JlHookTable = [
                [ 'testZonder', () => Promise.resolve({}) ],
                [ 'testGeenfunctie', () => Promise.resolve({ default: 'geen functie' }) ]
            ];
            const hook = createJlHook(tabel);

            await expect(hook('testZonder', {})).resolves.toBeUndefined();
            await expect(hook('testGeenfunctie', {})).resolves.toBeUndefined();
            expect(consoleRegels(warn)).toEqual([
                regel('testZonder', GEEN_HANDLER),
                regel('testGeenfunctie', GEEN_HANDLER)
            ]);
        });

        it('should return without exception when the table entry is not a loader', async () => {
            const warn = stilConsole();
            const tabel = [ [ 'testKapot', 'geen lader' ] ] as unknown as JlHookTable;

            await expect(createJlHook(tabel)('testKapot', {})).resolves.toBeUndefined();
            expect(consoleRegels(warn)).toEqual([ regel('testKapot', ONBEKENDE_NAAM) ]);
        });

        it('should return without exception when the table or an entry is broken', async () => {
            const warn = stilConsole();
            const kapotteRegel = [ null, 'testLos' ] as unknown as JlHookTable;
            const geenLijst = { testObject: () => Promise.resolve({ default: vi.fn() }) } as unknown as JlHookTable;

            await expect(createJlHook(kapotteRegel)('testLos', {})).resolves.toBeUndefined();
            await expect(createJlHook(geenLijst)('testObject', {})).resolves.toBeUndefined();
            expect(consoleRegels(warn)).toEqual([
                regel('testLos', ONBEKENDE_NAAM),
                regel('testObject', ONBEKENDE_NAAM)
            ]);
        });

        it('should never throw synchronously, even when the console itself fails', async () => {
            vi.spyOn(console, 'warn').mockImplementation(() => {
                throw new Error('console kapot');
            });
            const hook = createJlHook([]);
            let belofte: Promise<unknown> | undefined;

            expect(() => {
                belofte = hook('testOnbekend', {});
            }).not.toThrow();
            await expect(belofte).resolves.toBeUndefined();
        });
    });

    describe('Aanroep zonder await (regel voor upstream-haken)', () => {
        it('should not block a caller that does not await, even when the handler never settles', async () => {
            const nooit = vi.fn(() => new Promise<never>(() => { /* rondt nooit af */ }));
            const tabel: JlHookTable = [
                [ 'testNooit', () => Promise.resolve({ default: nooit }) ],
                [ 'testDaarna', () => Promise.resolve({ default: () => 'daarna' }) ]
            ];
            const hook = createJlHook(tabel);
            const volgorde: string[] = [];

            // Zoals een upstream-plek die het scherm tekent: aanroepen en doorgaan, niet wachten.
            const belofte = hook('testNooit', {});
            volgorde.push('aanroeper gaat door');
            const stand = await Promise.race([
                belofte.then(() => 'afgerond'),
                new Promise(resolve => setTimeout(() => resolve('open'), 50))
            ]);

            expect(volgorde).toEqual([ 'aanroeper gaat door' ]);
            expect(nooit).toHaveBeenCalledTimes(1);
            // Geen time-out (bewust): wie wel wacht, wacht op de handler. Daarom de regel in de kop van de module.
            expect(stand).toBe('open');
            // Een hangende handler houdt een andere haak niet op.
            await expect(hook('testDaarna', {})).resolves.toBe('daarna');
        });
    });

    describe('Soort fout (jlHookErrorKind)', () => {
        it('should give the error name or the type, never the message', () => {
            expect(jlHookErrorKind(new TypeError(GEHEIM))).toBe('TypeError');
            expect(jlHookErrorKind(GEHEIM)).toBe('string');
            expect(jlHookErrorKind(undefined)).toBe('undefined');
        });

        it('should fall back to "onbekend" when reading the error itself fails', () => {
            expect(() => jlHookErrorKind(foutMetGooiendeNaam())).not.toThrow();
            expect(jlHookErrorKind(foutMetGooiendeNaam())).toBe('onbekend');
            expect(jlHookErrorKind(ingetrokkenProxy())).toBe('onbekend');
        });
    });
});
