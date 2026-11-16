import React, { act, useCallback, useState } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { JlHookContext, JlHookTable } from './index';
import { createJlHookSlot, JlHookSlot } from './JlHookSlot';

const GEHEIM = 'gebruiker-geheim-5678';

declare global {
    var IS_REACT_ACT_ENVIRONMENT: boolean | undefined;
}

/** Een fout tijdens het tekenen meldt React (dev) en jsdom op de console; dat is hier verwacht. */
function onderdrukFoutmeldingen(event: ErrorEvent) {
    event.preventDefault();
}

describe('Jelly Leon: render-slot (JlHookSlot)', () => {
    let container: HTMLDivElement;
    let root: Root;
    let warn: ReturnType<typeof vi.spyOn>;

    beforeEach(() => {
        globalThis.IS_REACT_ACT_ENVIRONMENT = true;
        container = document.createElement('div');
        document.body.appendChild(container);
        root = createRoot(container);
        warn = vi.spyOn(console, 'warn').mockImplementation(() => { /* stil in de test */ });
        vi.spyOn(console, 'error').mockImplementation(() => { /* React meldt gevangen fouten */ });
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
        const Slot = createJlHookSlot({
            'testSlot': () => Promise.resolve({
                default: ({ ctx }: { ctx: JlHookContext }) => <b id='fork'>{String(ctx.titel)}</b>
            })
        });

        await render(<Omgeving><Slot name='testSlot' ctx={{ titel: 'fork-item' }} /></Omgeving>);

        expect(container.querySelector('#fork')?.textContent).toBe('fork-item');
        expect(container.textContent).toBe('upstream voorfork-itemupstream na');
    });

    it('should render nothing with the real (empty) table', async () => {
        await render(<Omgeving><JlHookSlot name='syncplay.menu' ctx={{ gebruiker: GEHEIM }} /></Omgeving>);

        expect(container.textContent).toBe('upstream voorupstream na');
        expect(consoleTekst()).not.toContain(GEHEIM);
    });

    describe('Negatief: het upstream-scherm blijft staan', () => {
        it('should render nothing and keep the surrounding content when the handler throws', async () => {
            const Slot = createJlHookSlot({
                'testGooit': () => Promise.resolve({
                    default: ({ ctx }: { ctx: JlHookContext }) => {
                        throw new Error(`kapot voor ${String(ctx.gebruiker)}`);
                    }
                })
            });

            await render(<Omgeving><Slot name='testGooit' ctx={{ gebruiker: GEHEIM }} /></Omgeving>);

            expect(container.textContent).toBe('upstream voorupstream na');
            expect(container.querySelector('#voor')).not.toBeNull();
            expect(container.querySelector('#na')).not.toBeNull();
            expect(warn).toHaveBeenCalledTimes(1);
            expect(consoleTekst()).toContain('testGooit');
            expect(consoleTekst()).not.toContain(GEHEIM);
        });

        it('should keep the upstream screen interactive after a failing handler', async () => {
            const Slot = createJlHookSlot({
                'testGooit': () => Promise.resolve({
                    default: () => {
                        throw new Error('kapot');
                    }
                })
            });

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
            const Slot = createJlHookSlot({
                'testImport': () => Promise.reject(new Error(`chunk ${GEHEIM} niet gevonden`))
            });

            await render(<Omgeving><Slot name='testImport' /></Omgeving>);

            expect(container.textContent).toBe('upstream voorupstream na');
            expect(warn).toHaveBeenCalledTimes(1);
            expect(consoleTekst()).not.toContain(GEHEIM);
        });

        it('should render nothing for an unknown name', async () => {
            const Slot = createJlHookSlot({
                'testBekend': () => Promise.resolve({ default: () => <b>fork</b> })
            });

            await render(<Omgeving><Slot name='testOnbekend' /></Omgeving>);

            expect(container.textContent).toBe('upstream voorupstream na');
            expect(warn).toHaveBeenCalledTimes(1);
        });

        it('should render nothing when the module has no component', async () => {
            const tabel: JlHookTable = {
                'testZonder': () => Promise.resolve({ default: 'geen onderdeel' })
            };
            const Slot = createJlHookSlot(tabel);

            await render(<Omgeving><Slot name='testZonder' /></Omgeving>);

            expect(container.textContent).toBe('upstream voorupstream na');
            expect(warn).toHaveBeenCalledTimes(1);
        });

        it('should not update state after unmount while the import is pending', async () => {
            let laat: (waarde: { default: unknown }) => void = () => { /* wordt hieronder gezet */ };
            const Slot = createJlHookSlot({
                'testTraag': () => new Promise(resolve => {
                    laat = resolve;
                })
            });

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
