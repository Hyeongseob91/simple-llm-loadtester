"use client";

import { Construction } from "lucide-react";

export default function RecommendPage() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[70vh]">
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-16 text-center w-[400px]">
        <Construction className="h-16 w-16 text-amber-500 mx-auto mb-6" />
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-3">
          준비중
        </h1>
        <p className="text-gray-600 dark:text-gray-400">
          이 기능은 현재 개발 중입니다.
        </p>
        <p className="text-sm text-gray-500 dark:text-gray-500 mt-4">
          Coming Soon
        </p>
      </div>
    </div>
  );
}
