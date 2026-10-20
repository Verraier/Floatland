#pragma once
#include <algorithm>
#include <cstdint>
namespace Floatland {
// Page preparation owns no windows or textures. Tokens reject obsolete IPC work.
struct SwitcherPreparation {
    uint64_t generation=0;
    int cursor=0,end=0;
    void cancel() { ++generation;cursor=end=0; }
    uint64_t begin(int first,int limit) {
        cancel();cursor=std::max(0,first);end=std::max(cursor,limit);return generation;
    }
    bool pending(uint64_t token) const { return token==generation && cursor<end; }
    int take(uint64_t token) { return pending(token)?cursor++:-1; }
};
}
