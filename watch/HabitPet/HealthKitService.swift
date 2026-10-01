import Foundation
import HealthKit

final class HealthKitService {
    private let store = HKHealthStore()
    private let stepsType = HKQuantityType.quantityType(forIdentifier: .stepCount)!
    private let sleepType = HKCategoryType.categoryType(forIdentifier: .sleepAnalysis)!
    func authorize() async throws {
        guard HKHealthStore.isHealthDataAvailable() else { throw APIError(status: 0, detail: "Health data is unavailable on this device.") }
        try await store.requestAuthorization(toShare: [], read: [stepsType, sleepType])
    }
    private var observers: [HKObserverQuery] = []
    func observeChanges(_ changed: @escaping () -> Void) {
        guard observers.isEmpty, HKHealthStore.isHealthDataAvailable() else { return }
        for type in [stepsType as HKSampleType, sleepType as HKSampleType] {
            let query=HKObserverQuery(sampleType:type,predicate:nil) { _,completion,error in
                if error == nil { changed() }
                completion()
            }
            observers.append(query); store.execute(query)
        }
    }
    func readBatch(_ batch: FitnessBatch, timezone identifier: String, now: Date) async throws -> [HealthDayInput] {
        let calendar=FitnessCalendar.calendar(identifier)
        var result:[HealthDayInput]=[]
        for day in batch.days {
            try Task.checkCancellation()
            let stepWindow=FitnessCalendar.stepWindow(day,calendar:calendar)
            let sleepWindow=FitnessCalendar.sleepWindow(day,calendar:calendar)
            async let steps=readSteps(start:stepWindow.start,end:min(now,stepWindow.end))
            async let sleep=readSleep(start:sleepWindow.start,end:min(now,sleepWindow.end))
            result.append(try await HealthDayInput(date:FitnessCalendar.key(day,calendar:calendar),steps:steps,sleepMinutes:sleep))
        }
        return result
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
