#pragma once
#include <memory>
namespace Floatland {
// Non-owning reference for deferred compositor work; it must not prolong an
// object's life, and must reject address reuse after its owner is destroyed.
template <typename T> class DeferredPtr {
  public:
    DeferredPtr(T* value, std::weak_ptr<int> lifetime) : value(value), lifetime(lifetime) {}
    T* get() const { return lifetime.expired() ? nullptr : value; }
  private:
    T* value;
    std::weak_ptr<int> lifetime;
};
}
