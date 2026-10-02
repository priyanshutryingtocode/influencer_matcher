interface RangeControlProps {
  id: string;
  label: string;
  value: number;
  min: number;
  max: number;
  onChange: (value: number) => void;
}

export function RangeControl({ id, label, value, min, max, onChange }: RangeControlProps) {
  const labelId = `${id}-label`;
  return (
    <label className="range-control" htmlFor={id}>
      {/* The caption and the live value share a flex row, so wrapping both in
       * the <label> made the input's accessible name "Candidates retrieved10" and
       * changed it while dragging. Name from the caption, spell the value out in
       * aria-valuetext. */}
      <span><span id={labelId}>{label}</span><strong>{value}</strong></span>
      <input
        id={id}
        type="range"
        min={min}
        max={max}
        value={value}
        aria-labelledby={labelId}
        aria-valuetext={`${value} creators`}
        onChange={(event) => onChange(Number(event.target.value))}
      />
    </label>
  );
}
