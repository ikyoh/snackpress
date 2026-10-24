import { describe, expect, it } from 'vitest'
import { barcodeCaption, barcodeError, newRepiquage, parseCsv, repiquageValue } from './fortuneData'

const csv = (text: string) => parseCsv(new TextEncoder().encode(text).buffer as ArrayBuffer)

describe('repiquages et données CSV', () => {
  it('importe les guillemets, retours à la ligne, accents et zéros initiaux sans typage numérique', () => {
    const data = csv('\uFEFFnom;code\r\n"Élodie; Atelier";00017\r\n"Zoé\nÉquipe";00018\r\n')
    expect(data).toEqual({
      columns: ['nom', 'code'],
      rows: [
        ['Élodie; Atelier', '00017'],
        ['Zoé\nÉquipe', '00018'],
      ],
    })
    expect(
      repiquageValue({ ...newRepiquage(55), source: 'csv', column: 'code' }, 'SP-0001', data),
    ).toBe('00017')
  })
  it('accepte une seule colonne et les tabulations', () => {
    expect(csv('nom\nAlice\nBob').rows).toEqual([['Alice'], ['Bob']])
    expect(csv('nom\tcode\nAlice\t0001').rows[0]).toEqual(['Alice', '0001'])
  })
  it.each(['nom;nom\nA;B', 'nom;code\nA', 'nom;code\n"A;B', 'nom\n'])(
    'refuse les en-têtes ou lignes invalides : %s',
    (text) => {
      expect(() => csv(text)).toThrow()
    },
  )
  it('refuse plus de 1000 lignes', () => {
    expect(() => csv('nom\n' + Array(1001).fill('A').join('\n'))).toThrow('1 000')
  })
  it('vérifie les codes sans modifier les valeurs CSV', () => {
    expect(barcodeError('590123412345', 'ean13')).toBe('')
    expect(barcodeError('5901234123457', 'ean13')).toBe('')
    expect(barcodeError('5901234123458', 'ean13')).toContain('clé')
    expect(barcodeError('00017', 'code128')).toBe('')
    expect(barcodeError('Élodie', 'code128')).toContain('ASCII')
    expect(barcodeCaption('00017', 'code128')).toBe('00017')
    expect(barcodeCaption('590123412345', 'ean13')).toBe('5901234123457')
    expect(barcodeCaption('5901234123457', 'ean13')).toBe('5901234123457')
  })
})
