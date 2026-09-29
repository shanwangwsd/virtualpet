import Foundation
import HealthKit

final class HealthKitService {
    private let store = HKHealthStore()
    private let stepsType = HKQuantityType.quantityType(forIdentifier: .stepCount)!
    private let sleepType = HKCategoryType.categoryType(forIdentifier: .sleepAnalysis)!
    func authorize() async throws {
        guard HKHealthStore.isHealthDataAvailable() else { throw APIError(status: 0, detail: "此设备暂不支持健康数据") }
        try await store.requestAuthorization(toShare: [], read: [stepsType, sleepType])
    }
    func summary(timezone identifier: String) async throws -> (steps: Int?, sleep: Int?) {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = TimeZone(identifier: identifier) ?? .current
        let now = Date(); let start = calendar.startOfDay(for: now)
        // Previous noon → current noon (clipped to now); merge asleep intervals only.
        let noon = calendar.date(bySettingHour: 12, minute: 0, second: 0, of: now)!
        let windowStart = calendar.date(byAdding: .day, value: -1, to: noon)!
        async let steps = readSteps(start: start, end: now)
        async let sleep = readSleep(start: windowStart, end: min(now, noon))
        return try await (steps, sleep)
    }
    private func readSteps(start: Date, end: Date) async throws -> Int? {
        try await withCheckedThrowingContinuation { continuation in
            let predicate = HKQuery.predicateForSamples(withStart: start, end: end, options: .strictStartDate)
            let query = HKStatisticsQuery(quantityType: stepsType, quantitySamplePredicate: predicate, options: .cumulativeSum) { _, statistics, error in
                if let error { continuation.resume(throwing: error); return }
                continuation.resume(returning: statistics?.sumQuantity().map { Int($0.doubleValue(for: .count())) })
            }
            store.execute(query)
        }
    }
    private func readSleep(start: Date, end: Date) async throws -> Int? {
        try await withCheckedThrowingContinuation { continuation in
            let predicate = HKQuery.predicateForSamples(withStart: start, end: end, options: [])
            let query = HKSampleQuery(sampleType: sleepType, predicate: predicate, limit: HKObjectQueryNoLimit, sortDescriptors: nil) { _, samples, error in
                if let error { continuation.resume(throwing: error); return }
                let asleep = (samples as? [HKCategorySample] ?? []).filter { sample in
                    guard let value = HKCategoryValueSleepAnalysis(rawValue: sample.value) else { return false }
                    return HKCategoryValueSleepAnalysis.allAsleepValues.contains(value)
                }
                guard !asleep.isEmpty else { continuation.resume(returning: nil); return }
                let intervals = asleep.map { SleepInterval(start: $0.startDate, end: $0.endDate) }
                continuation.resume(returning: SleepMath.minutes(intervals, from: start, to: end))
            }
            store.execute(query)
        }
    }
}
