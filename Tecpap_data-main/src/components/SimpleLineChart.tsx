interface DataPoint {
  label: string;
  value: number;
}

interface SimpleLineChartProps {
  data: DataPoint[];
  title: string;
  color?: string;
  valueFormatter?: (value: number) => string;
}

export function SimpleLineChart({
  data,
  title,
  color = '#2563eb',
  valueFormatter = (v) => v.toFixed(1),
}: SimpleLineChartProps) {
  if (!data || data.length === 0) {
    return (
      <div className="bg-gray-50 rounded p-6 text-center text-gray-500">
        No data available
      </div>
    );
  }

  const maxValue = Math.max(...data.map((d) => d.value), 1);
  const minValue = Math.min(...data.map((d) => d.value), 0);
  const range = maxValue - minValue || 1;

  const chartHeight = 200;
  const chartWidth = 600;
  const padding = 40;

  const points = data
    .map((point, index) => {
      const x = padding + (index / (data.length - 1 || 1)) * (chartWidth - padding * 2);
      const y =
        chartHeight -
        padding -
        ((point.value - minValue) / range) * (chartHeight - padding * 2);
      return `${x},${y}`;
    })
    .join(' ');

  return (
    <div className="bg-white rounded-lg border p-4">
      <h4 className="font-semibold mb-4">{title}</h4>
      <svg
        viewBox={`0 0 ${chartWidth} ${chartHeight}`}
        className="w-full"
        style={{ maxHeight: '250px' }}
      >
        <polyline
          points={points}
          fill="none"
          stroke={color}
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        {data.map((point, index) => {
          const x = padding + (index / (data.length - 1 || 1)) * (chartWidth - padding * 2);
          const y =
            chartHeight -
            padding -
            ((point.value - minValue) / range) * (chartHeight - padding * 2);

          return (
            <g key={index}>
              <circle cx={x} cy={y} r="4" fill={color} />
              <text
                x={x}
                y={chartHeight - 10}
                textAnchor="middle"
                fontSize="10"
                fill="#666"
              >
                {point.label}
              </text>
            </g>
          );
        })}

        <line
          x1={padding}
          y1={chartHeight - padding}
          x2={chartWidth - padding}
          y2={chartHeight - padding}
          stroke="#ddd"
          strokeWidth="1"
        />

        <text x="10" y="20" fontSize="12" fill="#666">
          {valueFormatter(maxValue)}
        </text>
        <text x="10" y={chartHeight - padding + 5} fontSize="12" fill="#666">
          {valueFormatter(minValue)}
        </text>
      </svg>
    </div>
  );
}
