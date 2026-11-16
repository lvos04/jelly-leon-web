import { describe, expect, it, vi } from 'vitest';
import { createJlHook, jlHook, jlHookErrorKind, JL_HOOK_HANDLERS, type JlHookTable } from './index';

const GEHEIM = 'gebruiker-geheim-1234';

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

describe('Jelly Leon: haakmodule (jlHook)', () => {
    describe('Tabel', () => {
        it('should have an empty handler table (no hook is placed yet)', () => {
            expect(Object.keys(JL_HOOK_HANDLERS)).toEqual([]);
        });

        it('should return without exception for any name with the real (empty) table', async () => {
            const warn = stilConsole();

            await expect(jlHook('syncplay.menu', { gebruiker: GEHEIM })).resolves.toBeUndefined();
            expect(warn).toHaveBeenCalledTimes(1);
            expect(consoleTekst(warn)).not.toContain(GEHEIM);
        });
    });

    describe('Normaal pad', () => {
        it('should load the handler with a dynamic import and call it with the context', async () => {
            const handler = vi.fn(() => 'resultaat');
            const tabel: JlHookTable = {
                'testHaak': () => Promise.resolve({ default: handler })
            };
            const ctx = { itemId: 'abc' };

            await expect(createJlHook(tabel)('testHaak', ctx)).resolves.toBe('resultaat');
            expect(handler).toHaveBeenCalledTimes(1);
            expect(handler).toHaveBeenCalledWith(ctx);
        });

        it('should await an async handler and return its result', async () => {
            const tabel: JlHookTable = {
                'testAsync': () => Promise.resolve({ default: () => Promise.resolve(42) })
            };

            await expect(createJlHook(tabel)('testAsync', {})).resolves.toBe(42);
        });

        it('should pass an empty context when none is given', async () => {
            const handler = vi.fn();
            const tabel: JlHookTable = { 'testLeeg': () => Promise.resolve({ default: handler }) };

            await createJlHook(tabel)('testLeeg');

            expect(handler).toHaveBeenCalledWith({});
        });
    });

    describe('Negatief: de aanroeper breekt nooit', () => {
        it('should return without exception when the handler throws', async () => {
            const warn = stilConsole();
            const tabel: JlHookTable = {
                'testGooit': () => Promise.resolve({
                    default: (ctx: Readonly<Record<string, unknown>>) => {
                        throw new Error(`kapot voor ${String(ctx.gebruiker)}`);
                    }
                })
            };

            await expect(createJlHook(tabel)('testGooit', { gebruiker: GEHEIM })).resolves.toBeUndefined();
            expect(warn).toHaveBeenCalledTimes(1);
            expect(consoleTekst(warn)).toContain('testGooit');
            expect(consoleTekst(warn)).not.toContain(GEHEIM);
        });

        it('should return without exception when an async handler rejects', async () => {
            const warn = stilConsole();
            const tabel: JlHookTable = {
                'testWeigert': () => Promise.resolve({
                    default: () => Promise.reject(new Error(GEHEIM))
                })
            };

            await expect(createJlHook(tabel)('testWeigert', {})).resolves.toBeUndefined();
            expect(warn).toHaveBeenCalledTimes(1);
            expect(consoleTekst(warn)).not.toContain(GEHEIM);
        });

        it('should return without exception when the handler throws a value whose kind cannot be read', async () => {
            const warn = stilConsole();
            const tabel: JlHookTable = {
                'testNaamGetter': () => Promise.resolve({
                    default: () => {
                        throw foutMetGooiendeNaam();
                    }
                }),
                'testProxy': () => Promise.resolve({
                    default: () => Promise.reject(ingetrokkenProxy())
                })
            };
            const hook = createJlHook(tabel);

            await expect(hook('testNaamGetter', {})).resolves.toBeUndefined();
            await expect(hook('testProxy', {})).resolves.toBeUndefined();
            expect(warn).toHaveBeenCalledTimes(2);
            expect(consoleTekst(warn)).toContain('"testNaamGetter": handler gaf een fout (onbekend)');
            expect(consoleTekst(warn)).toContain('"testProxy": handler gaf een fout (onbekend)');
            expect(consoleTekst(warn)).not.toContain(GEHEIM);
        });

        it('should return without exception when the import fails with a value whose kind cannot be read', async () => {
            const warn = stilConsole();
            const tabel: JlHookTable = {
                'testImportNaam': () => Promise.reject(foutMetGooiendeNaam()),
                'testImportProxy': () => Promise.reject(ingetrokkenProxy())
            };
            const hook = createJlHook(tabel);

            await expect(hook('testImportNaam', {})).resolves.toBeUndefined();
            await expect(hook('testImportProxy', {})).resolves.toBeUndefined();
            expect(warn).toHaveBeenCalledTimes(2);
            expect(consoleTekst(warn)).toContain('"testImportNaam": laden mislukt (onbekend)');
            expect(consoleTekst(warn)).toContain('"testImportProxy": laden mislukt (onbekend)');
        });

        it('should return without exception when the import fails', async () => {
            const warn = stilConsole();
            const tabel: JlHookTable = {
                'testImport': () => Promise.reject(new Error(`chunk ${GEHEIM} niet gevonden`))
            };

            await expect(createJlHook(tabel)('testImport', {})).resolves.toBeUndefined();
            expect(warn).toHaveBeenCalledTimes(1);
            expect(consoleTekst(warn)).toContain('testImport');
            expect(consoleTekst(warn)).not.toContain(GEHEIM);
        });

        it('should return without exception when the loader itself throws synchronously', async () => {
            const warn = stilConsole();
            const tabel: JlHookTable = {
                'testLader': () => {
                    throw new Error(GEHEIM);
                }
            };

            await expect(createJlHook(tabel)('testLader', {})).resolves.toBeUndefined();
            expect(warn).toHaveBeenCalledTimes(1);
        });

        it('should return without exception for an unknown name', async () => {
            const warn = stilConsole();
            const tabel: JlHookTable = {
                'testBekend': () => Promise.resolve({ default: vi.fn() })
            };

            await expect(createJlHook(tabel)('testOnbekend', { gebruiker: GEHEIM })).resolves.toBeUndefined();
            expect(warn).toHaveBeenCalledTimes(1);
            expect(consoleTekst(warn)).toContain('testOnbekend');
            expect(consoleTekst(warn)).not.toContain(GEHEIM);
        });

        it('should not treat names from the object prototype as handlers', async () => {
            const warn = stilConsole();
            const hook = createJlHook({});

            await expect(hook('constructor', {})).resolves.toBeUndefined();
            await expect(hook('toString', {})).resolves.toBeUndefined();
            await expect(hook('__proto__', {})).resolves.toBeUndefined();
            expect(warn).toHaveBeenCalledTimes(3);
        });

        it('should return without exception when the module has no handler function', async () => {
            const warn = stilConsole();
            const tabel: JlHookTable = {
                'testZonder': () => Promise.resolve({}),
                'testGeenfunctie': () => Promise.resolve({ default: 'geen functie' })
            };
            const hook = createJlHook(tabel);

            await expect(hook('testZonder', {})).resolves.toBeUndefined();
            await expect(hook('testGeenfunctie', {})).resolves.toBeUndefined();
            expect(warn).toHaveBeenCalledTimes(2);
        });

        it('should return without exception when the table entry is not a loader', async () => {
            const warn = stilConsole();
            const tabel = { 'testKapot': 'geen lader' } as unknown as JlHookTable;

            await expect(createJlHook(tabel)('testKapot', {})).resolves.toBeUndefined();
            expect(warn).toHaveBeenCalledTimes(1);
        });

        it('should never throw synchronously, even when the console itself fails', async () => {
            vi.spyOn(console, 'warn').mockImplementation(() => {
                throw new Error('console kapot');
            });
            const hook = createJlHook({});
            let belofte: Promise<unknown> | undefined;

            expect(() => {
                belofte = hook('testOnbekend', {});
            }).not.toThrow();
            await expect(belofte).resolves.toBeUndefined();
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
