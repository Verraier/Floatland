#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>
namespace Floatland {
// All timestamps are monotonic seconds supplied by the caller. This state
// machine owns transitions; GPU resource release happens only at frame start.
class OverviewFlow {
  public:
    enum class Stage { Hidden, Preparing, Entering, Visible, Selecting, Exiting };
    Stage stage=Stage::Hidden;
    uint64_t generation=0;
    double start=0, from=0, target=0, duration=.24, enterSeconds=.24, exitSeconds=.24;
    void reset() { ++generation; stage=Stage::Hidden; from=target=0; }
    uint64_t prepare() { reset(); stage=Stage::Preparing; return generation; }
    bool accepts(uint64_t token) const { return token==generation && stage==Stage::Preparing; }
    bool presenting() const { return stage!=Stage::Hidden && stage!=Stage::Preparing; }
    double value(double now) const {
        if (!presenting()) return 0;
        if (stage==Stage::Selecting) return from;
        const double t=std::clamp((now-start)/duration,0.0,1.0);
        const double ease=t*t*(3-2*t);
        return from+(target-from)*ease;
    }
    void move(bool open,double now) {
        from=value(now); target=open?1:0; start=now;
        duration=std::max(.035,(open?enterSeconds:exitSeconds)*std::abs(target-from));
        stage=open?Stage::Entering:Stage::Exiting;
    }
    void ready(uint64_t token,double now) {
        if (!accepts(token)) return;
        from=0; target=0; start=now; stage=Stage::Entering; move(true,now);
    }
    void toggle(double now) {
        if (stage==Stage::Preparing) { reset(); return; }
        if (stage==Stage::Selecting || stage==Stage::Hidden) return;
        move(stage==Stage::Exiting,now);
    }
    void close(double now) { if (stage==Stage::Preparing) reset(); else if (presenting() && stage!=Stage::Exiting) move(false,now); }
    void select(double now) { from=value(now); start=now; stage=Stage::Selecting; }
    bool selectionExpired(double now) const { return stage==Stage::Selecting && now-start>=3; }
    bool finishFrame(double now) {
        if (stage==Stage::Entering && now-start>=duration) stage=Stage::Visible;
        return stage==Stage::Exiting && now-start>=duration;
    }
};
}
