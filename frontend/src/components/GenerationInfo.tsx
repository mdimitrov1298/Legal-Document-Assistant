import { formatDuration } from '@/utils/format'

interface GenerationInfoProps {
  model: string
  stubbed: boolean
  durationMs: number
  /** Number of retrieved chunks passed to the model, when known. */
  chunksUsed?: number
}

export function GenerationInfo({ model, stubbed, durationMs, chunksUsed }: GenerationInfoProps) {
  return (
    <>
      {stubbed && (
        <p className="notice notice--warn" role="status">
          Отговорът е заглушка: Ollama не е достъпен. Показаните цитати са сурови откъси от
          документите, а не резултат от модела.
        </p>
      )}
      <p className="generation-info">
        <span className="model-tag" title="Използван модел">
          {model}
        </span>
        {stubbed && <span className="model-tag model-tag--stub">заглушка</span>}
        <span>Време: {formatDuration(durationMs)}</span>
        {chunksUsed !== undefined && <span>Използвани фрагменти: {chunksUsed}</span>}
      </p>
    </>
  )
}
