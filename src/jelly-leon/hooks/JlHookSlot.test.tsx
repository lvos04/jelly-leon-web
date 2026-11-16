import React, { act, forwardRef, memo, StrictMode, useCallback, useState } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { JlHookContext, JlHookModule, JlHookTable } from './index';
import { createJlHookSlot, JlHookSlot } from './JlHookSlot';

const GEHEIM = 'gebruiker-geheim-5678';

/** De vaste reden in de consoleregel als de standaardexport geen React-onderdeel is. */
const GEEN_ONDERDEEL = 'module heeft geen onderdeel (standaardexport is geen functie-, klasse-, memo- of forwardRef-onderdeel)';

/** De consoleregel die de module voor deze haak en deze reden schrijft. */
function regel(naam: string, reden: string) {
    return `[Jelly Leon] haak "${naam}": ${reden}`;
}

declare global {
    var IS_REACT_ACT_ENVIRONMENT: boolean | undefined;
}

/**
 * Een fout tijdens het tekenen meldt React (dev) en jsdom op de console. In de meeste tests is dat ruis en wordt de
 * melding hier onderdrukt; de test "should leave the full error to the console log of React" legt dat gedrag vast.
 */
function onderdrukFoutmeldingen(event: ErrorEvent) {
    event.preventDefault();
}

describe('Jelly Leon: render-slot (JlHookSlot)', () => {
    let container: HTMLDivElement;
    let root: Root;
    let warn: ReturnType<typeof vi.spyOn>;
    let fout: ReturnType<typeof vi.spyOn>;

    beforeEach(() => {
        globalThis.IS_REACT_ACT_ENVIRONMENT = true;
        container = document.createElement('div');
        document.body.appendChild(container);
        root = createRoot(container);
        warn = vi.spyOn(console, 'warn').mockImplementation(() => { /* stil in de test */ });
        fout = vi.spyOn(console, 'error').mockImplementation(() => { /* gecontroleerd in de test over React-logs */ });
        window.addEventListener('error', onderdrukFoutmeldingen);
    });

    afterEach(() => {
        act(() => root.unmount());
        container.remove();
        window.removeEventListener('error', onderdrukFoutmeldingen);
        globalThis.IS_REACT_ACT_ENVIRONMENT = undefined;
    });

    /** Rendert het slot tussen upstream-inhoud en wacht tot de dynamische import is afgehandeld. */
    async function render(element: React.ReactElement) {
        await act(async () => {
            root.render(element);
        });
        await act(async () => { /* microtaken van import() en setState afwerken */ });
    }

    function consoleTekst() {
        return warn.mock.calls.map(args => args.map(String).join(' ')).join('\n');
    }

    function consoleRegels() {
        return warn.mock.calls.map(args => args.map(String).join(' '));
    }

    /** Alles wat op console.error kwam, met naam, melding en stack van een Error. */
    function foutTekst() {
        return fout.mock.calls
            .map(args => args.map(arg => (arg instanceof Error ? `${arg.name}: ${arg.message} ${String(arg.stack)}` : String(arg))).join(' '))
            .join('\n');
    }

    function Omgeving({ children }: Readonly<{ children: React.ReactNode }>) {
        return (
            <div>
                <span id='voor'>upstream voor</span>
                {children}
                <span id='na'>upstream na</span>
            </div>
        );
    }

    it('should render the handler component with the context', async () => {
        const Slot = createJlHookSlot([
            [ 'testSlot', () => Promise.resolve({
                default: ({ ctx }: { ctx: JlHookContext }) => <b id='fork'>{String(ctx.titel)}</b>
            }) ]
        ]);

        await render(<Omgeving><Slot name='testSlot' ctx={{ titel: 'fork-item' }} /></Omgeving>);

        expect(container.querySelector('#fork')?.textContent).toBe('fork-item');
        expect(container.textContent).toBe('upstream voorfork-itemupstream na');
    });

    it('should render memo and forwardRef components', async () => {
        const MemoOnderdeel = memo(function MemoTekst({ ctx }: Readonly<{ ctx: JlHookContext }>) {
            return <b>{`memo-${String(ctx.titel)}`}</b>;
        });
        const RefOnderdeel = forwardRef<HTMLElement, Readonly<{ ctx: JlHookContext }>>(function RefTekst({ ctx }, ref) {
            return <i ref={ref}>{`ref-${String(ctx.titel)}`}</i>;
        });
        const Slot = createJlHookSlot([
            [ 'testMemo', () => Promise.resolve({ default: MemoOnderdeel }) ],
            [ 'testRef', () => Promise.resolve({ default: RefOnderdeel }) ]
        ]);

        await render(
            <Omgeving>
                <Slot name='testMemo' ctx={{ titel: 'x' }} />
                <Slot name='testRef' ctx={{ titel: 'y' }} />
            </Omgeving>
        );

        expect(container.textContent).toBe('upstream voormemo-xref-yupstream na');
        expect(warn).not.toHaveBeenCalled();
    });

    it('should render nothing with the real (empty) table', async () => {
        await render(<Omgeving><JlHookSlot name='syncplay.menu' ctx={{ gebruiker: GEHEIM }} /></Omgeving>);

        expect(container.textContent).toBe('upstream voorupstream na');
        expect(consoleTekst()).not.toContain(GEHEIM);
    });

    describe('Negatief: het upstream-scherm blijft staan', () => {
        it('should render nothing and keep the surrounding content when the handler throws', async () => {
            const Slot = createJlHookSlot([
                [ 'testGooit', () => Promise.resolve({
                    default: ({ ctx }: { ctx: JlHookContext }) => {
                        throw new Error(`kapot voor ${String(ctx.gebruiker)}`);
                    }
                }) ]
            ]);

            await render(<Omgeving><Slot name='testGooit' ctx={{ gebruiker: GEHEIM }} /></Omgeving>);

            expect(container.textContent).toBe('upstream voorupstream na');
            expect(container.querySelector('#voor')).not.toBeNull();
            expect(container.querySelector('#na')).not.toBeNull();
            expect(consoleRegels()).toEqual([ regel('testGooit', 'onderdeel gaf een fout (Error)') ]);
            expect(consoleTekst()).not.toContain(GEHEIM);
        });

        it('should leave the full error to the console log of React (so fork components keep user data out of errors)', async () => {
            // Hier geen onderdrukking: zo logt de browser (ontwikkeling) of React zelf (productie: console.error(fout)).
            window.removeEventListener('error', onderdrukFoutmeldingen);
            const Slot = createJlHookSlot([
                [ 'testLog', () => Promise.resolve({
                    default: ({ ctx }: { ctx: JlHookContext }) => {
                        throw new Error(`kapot voor ${String(ctx.gebruiker)}`);
                    }
                }) ]
            ]);

            await render(<Omgeving><Slot name='testLog' ctx={{ gebruiker: GEHEIM }} /></Omgeving>);

            expect(container.textContent).toBe('upstream voorupstream na');
            // De eigen consoleregel van het slot: zonder de foutmelding.
            expect(consoleRegels()).toEqual([ regel('testLog', 'onderdeel gaf een fout (Error)') ]);
            // De logregel van React (of de browser) bevat de foutmelding wel, met wat het onderdeel erin zette.
            expect(fout).toHaveBeenCalled();
            expect(foutTekst()).toContain(`kapot voor ${GEHEIM}`);
        });

        it('should keep the upstream screen interactive after a failing handler', async () => {
            const Slot = createJlHookSlot([
                [ 'testGooit', () => Promise.resolve({
                    default: () => {
                        throw new Error('kapot');
                    }
                }) ]
            ]);

            function Teller() {
                const [aantal, setAantal] = useState(0);
                const verhoog = useCallback(() => setAantal(n => n + 1), []);
                return (
                    <div>
                        <button id='knop' onClick={verhoog}>{aantal}</button>
                        <Slot name='testGooit' />
                    </div>
                );
            }

            await render(<Teller />);
            await act(async () => {
                container.querySelector<HTMLButtonElement>('#knop')?.click();
            });

            expect(container.querySelector('#knop')?.textContent).toBe('1');
        });

        it('should render nothing and keep the surrounding content when the import fails', async () => {
            const Slot = createJlHookSlot([
                [ 'testImport', () => Promise.reject(new Error(`chunk ${GEHEIM} niet gevonden`)) ]
            ]);

            await render(<Omgeving><Slot name='testImport' /></Omgeving>);

            expect(container.textContent).toBe('upstream voorupstream na');
            expect(consoleRegels()).toEqual([ regel('testImport', 'laden mislukt (Error)') ]);
            expect(consoleTekst()).not.toContain(GEHEIM);
        });

        it('should render nothing for an unknown name', async () => {
            const Slot = createJlHookSlot([
                [ 'testBekend', () => Promise.resolve({ default: () => <b>fork</b> }) ]
            ]);

            await render(<Omgeving><Slot name='testOnbekend' /></Omgeving>);

            expect(container.textContent).toBe('upstream voorupstream na');
            expect(consoleRegels()).toEqual([ regel('testOnbekend', 'onbekende naam of geen handler in de tabel') ]);
        });

        it('should render nothing when the module has no component', async () => {
            const tabel: JlHookTable = [
                [ 'testZonder', () => Promise.resolve({ default: 'geen onderdeel' }) ],
                [ 'testElement', () => Promise.resolve({ default: <b>een element, geen onderdeel</b> }) ]
            ];
            const Slot = createJlHookSlot(tabel);

            await render(<Omgeving><Slot name='testZonder' /><Slot name='testElement' /></Omgeving>);

            expect(container.textContent).toBe('upstream voorupstream na');
            expect(consoleRegels()).toEqual([
                regel('testZonder', GEEN_ONDERDEEL),
                regel('testElement', GEEN_ONDERDEEL)
            ]);
        });

        it('should ignore a slow load from an effect that React already cleaned up (StrictMode)', async () => {
            // StrictMode (upstream gebruikt het, src/components/Page.tsx) zet het effect in ontwikkeling op, af en weer
            // op in hetzelfde onderdeel. De eerste lading rondt hier pas als laatste af, met een ander onderdeel: zonder
            // de active-vlag in SlotLoader zou die oude lading het onderdeel van de tweede overschrijven.
            let laatEerste: (waarde: JlHookModule) => void = () => { /* wordt hieronder gezet */ };
            let aanroepen = 0;
            const Slot = createJlHookSlot([
                [ 'testStrikt', () => {
                    aanroepen += 1;
                    if (aanroepen === 1) {
                        return new Promise<JlHookModule>(resolve => {
                            laatEerste = resolve;
                        });
                    }
                    return Promise.resolve({ default: () => <b>nieuw</b> });
                } ]
            ]);

            await render(<StrictMode><Omgeving><Slot name='testStrikt' /></Omgeving></StrictMode>);
            expect(aanroepen).toBe(2);
            expect(container.textContent).toBe('upstream voornieuwupstream na');

            await act(async () => {
                laatEerste({ default: () => <b>oud</b> });
            });

            expect(container.textContent).toBe('upstream voornieuwupstream na');
        });

        it('should keep the surrounding content when a slow import finishes after unmount (smoke test)', async () => {
            // Rooktest: React 18 negeert setState na unmount zelf al; de active-vlag meet de test hierboven.
            let laat: (waarde: JlHookModule) => void = () => { /* wordt hieronder gezet */ };
            const Slot = createJlHookSlot([
                [ 'testTraag', () => new Promise<JlHookModule>(resolve => {
                    laat = resolve;
                }) ]
            ]);

            await render(<Omgeving><Slot name='testTraag' /></Omgeving>);
            await act(async () => {
                root.render(<Omgeving>{null}</Omgeving>);
            });
            await act(async () => {
                laat({ default: () => <b>te laat</b> });
            });

            expect(container.textContent).toBe('upstream voorupstream na');
        });
    });
});
