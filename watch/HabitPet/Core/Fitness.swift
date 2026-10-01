import Foundation

enum FitnessRules {
    static func steps(_ value: Int) -> Int { value >= 5000 ? 30 : value >= 1000 ? 10 : value >= 500 ? 0 : -10 }
    static func sleep(_ minutes: Int) -> Int { minutes >= 480 ? 10 : minutes >= 300 ? 0 : -10 }
}
struct HealthDayInput: Codable {
    var date: String
    var steps: Int?
    var sleepMinutes: Int?
    enum CodingKeys: String, CodingKey { case date, steps, sleepMinutes }
    func encode(to encoder: Encoder) throws {
        var c = encoder.container(keyedBy: CodingKeys.self)
        try c.encode(date, forKey: .date)
        try c.encode(steps, forKey: .steps)
        try c.encode(sleepMinutes, forKey: .sleepMinutes)
    }
}
struct HealthUpload: Encodable {
    var generation: Int
    var observedAt: Date
    var days: [HealthDayInput]
}
struct FitnessBatch {
    var days: [Date]
    var hasMore: Bool
}
enum FitnessCalendar {
    static func calendar(_ timezone: String) -> Calendar {
        var cal = Calendar(identifier: .gregorian)
        cal.timeZone = TimeZone(identifier: timezone) ?? .current
        return cal
    }
    static func formatter(_ calendar: Calendar) -> DateFormatter {
        let f=DateFormatter(); f.locale=Locale(identifier:"en_US_POSIX"); f.calendar=calendar
        f.timeZone=calendar.timeZone; f.dateFormat="yyyy-MM-dd"; f.isLenient=false
        return f
    }
    static func key(_ date: Date, calendar: Calendar) -> String { formatter(calendar).string(from: date) }
    static func date(_ key: String, calendar: Calendar) -> Date? { formatter(calendar).date(from: key) }
    static func stepWindow(_ date: Date, calendar: Calendar) -> DateInterval {
        let start=calendar.startOfDay(for: date)
        return DateInterval(start:start,end:calendar.date(byAdding:.day,value:1,to:start)!)
    }
    static func sleepWindow(_ date: Date, calendar: Calendar) -> DateInterval {
        let previous=calendar.date(byAdding:.day,value:-1,to:date)!
        let start=calendar.date(bySettingHour:18,minute:0,second:0,of:previous)!
        let end=calendar.date(bySettingHour:12,minute:0,second:0,of:date)!
        return DateInterval(start:start,end:end)
    }
    static func batch(start: String, lastSteps: String?, lastSleep: String?, timezone: String, now: Date) throws -> FitnessBatch {
        let cal=calendar(timezone)
        guard let first=date(start,calendar:cal) else { throw CocoaError(.coderReadCorrupt) }
        func next(_ cursor:String?) -> Date {
            guard let cursor,let date=date(cursor,calendar:cal) else { return first }
            return cal.date(byAdding:.day,value:1,to:date)!
        }
        let today=cal.startOfDay(for:now)
        var day=max(first,min(next(lastSteps),next(lastSleep)))
        var days:[Date]=[]
        while day<=today && days.count<14 {
            days.append(day)
            day=cal.date(byAdding:.day,value:1,to:day)!
        }
        let more=day<=today
        if !days.contains(today),today>=first { days.append(today) }
        return FitnessBatch(days:days,hasMore:more)
    }
}
