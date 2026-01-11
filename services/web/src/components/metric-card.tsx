import { clsx } from "clsx";
import { LucideIcon } from "lucide-react";

interface MetricCardProps {
  title: string;
  value: string | number;
  unit?: string;
  icon?: LucideIcon;
  trend?: "up" | "down" | "neutral";
  description?: string;
  className?: string;
}

export function MetricCard({
  title,
  value,
  unit,
  icon: Icon,
  trend,
  description,
  className,
}: MetricCardProps) {
  return (
    <div
      className={clsx(
        "bg-white dark:bg-gray-800 rounded-xl p-6 shadow-sm border border-gray-200 dark:border-gray-700",
        className
      )}
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium text-gray-500 dark:text-gray-400">
            {title}
          </p>
          <div className="mt-2 flex items-baseline gap-1">
            <span className="text-3xl font-bold text-gray-900 dark:text-white">
              {typeof value === "number" ? value.toLocaleString() : value}
            </span>
            {unit && (
              <span className="text-sm text-gray-500 dark:text-gray-400">
                {unit}
              </span>
            )}
          </div>
          {description && (
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              {description}
            </p>
          )}
        </div>
        {Icon && (
          <div
            className={clsx(
              "p-3 rounded-lg",
              trend === "up" && "bg-green-100 dark:bg-green-900/30",
              trend === "down" && "bg-red-100 dark:bg-red-900/30",
              (!trend || trend === "neutral") &&
                "bg-blue-100 dark:bg-blue-900/30"
            )}
          >
            <Icon
              className={clsx(
                "h-6 w-6",
                trend === "up" && "text-green-600 dark:text-green-400",
                trend === "down" && "text-red-600 dark:text-red-400",
                (!trend || trend === "neutral") &&
                  "text-blue-600 dark:text-blue-400"
              )}
            />
          </div>
        )}
      </div>
    </div>
  );
}
