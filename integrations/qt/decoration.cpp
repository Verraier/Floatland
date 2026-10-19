// Optional Qt client-side decoration. Built independently of the compositor plugin.
#include <QtWaylandClient/private/qwaylandabstractdecoration_p.h>
#include <QtWaylandClient/private/qwaylanddecorationplugin_p.h>
#include <QtWaylandClient/private/qwaylandwindow_p.h>
#include <QtWaylandClient/private/qwaylandshellsurface_p.h>
#include <QWindow>
#include <QPainter>
#include <QLinearGradient>
#include <QFile>
#include <QJsonDocument>
#include <QJsonObject>
#include <QGuiApplication>
#include <QTimer>
#include <QLocalSocket>
#include <QUuid>
#include <QDir>
#include <memory>
#include "../../native/geometry.hpp"

using namespace QtWaylandClient;

class FloatlandDecoration final : public QWaylandAbstractDecoration {
    Q_OBJECT
    QJsonObject settings;
    QByteArray lastSettings;
    Floatland::Control pressed=Floatland::Control::None;
    Floatland::Control hovered=Floatland::Control::None;
    bool tagged=false;
    QString appId;
    QTimer timer;
    static constexpr int border=3;
    bool left() const { return settings.value("buttons_side").toString("right")=="left"; }
    Floatland::ButtonOrder order() const {
        return Floatland::buttonOrder(settings.value("buttons_order").toString("maximize,minimize,close").toStdString());
    }
    QColor color(const char* key, const char* fallback) const {
        QColor value(settings.value(key).toString(QString::fromLatin1(fallback)));
        return value.isValid()?value:QColor(fallback);
    }
    Floatland::Control hit(const QPointF& p) const {
        return Floatland::hitButtonCircle({0,0,double(waylandWindow()->surfaceSize().width()),32},
                                         {p.x(),p.y()},left(),order());
    }
    void activate(Floatland::Control action) {
        if(action==Floatland::Control::None || appId.isEmpty()) return;
        const QString name=action==Floatland::Control::Close?"close":action==Floatland::Control::Minimize?"minimize":"maximize";
        const QString runtime=qEnvironmentVariable("XDG_RUNTIME_DIR");
        const QString instance=qEnvironmentVariable("HYPRLAND_INSTANCE_SIGNATURE");
        if(runtime.isEmpty() || instance.isEmpty()) { qWarning("Floatland daemon session is unavailable"); return; }
        auto socket=new QLocalSocket(qApp);
        auto response=std::make_shared<QByteArray>();
        auto timeout=new QTimer(socket); timeout->setSingleShot(true); timeout->start(3000);
        connect(timeout,&QTimer::timeout,socket,[socket]{ qWarning("Floatland action timed out; not retried"); socket->abort(); socket->deleteLater(); });
        connect(socket,&QLocalSocket::connected,socket,[socket,name,id=appId]{
            QJsonObject target{{"action",name},{"class",id},{"pid",double(QCoreApplication::applicationPid())}};
            socket->write(QJsonDocument(QJsonObject{{"action","qt-action"},{"value",target}}).toJson(QJsonDocument::Compact)+"\n");
        });
        connect(socket,&QLocalSocket::readyRead,socket,[socket,response]{
            response->append(socket->readAll());
            if(response->contains('\n')) {
                const auto reply=QJsonDocument::fromJson(*response).object();
                if(!reply.value("ok").toBool()) qWarning().noquote()<<"Floatland action rejected:"<<reply.value("error").toString();
                socket->disconnectFromServer();
            }
        });
        connect(socket,&QLocalSocket::disconnected,socket,&QObject::deleteLater);
        connect(socket,&QLocalSocket::errorOccurred,socket,[socket](QLocalSocket::LocalSocketError){ qWarning().noquote()<<"Floatland action:"<<socket->errorString();socket->deleteLater(); });
        socket->connectToServer(runtime+"/hypr/"+instance+"/floatland.sock");
    }
    void invalidate() {
        update();
        if(window()) window()->requestUpdate();
    }
    void readSettings() {
        QFile file(qEnvironmentVariable("FLOATLAND_QT_SETTINGS"));
        if(!file.open(QIODevice::ReadOnly)) return;
        const auto data=file.readAll();
        if(data==lastSettings) return;
        QJsonParseError error;
        const auto document=QJsonDocument::fromJson(data,&error);
        if(error.error!=QJsonParseError::NoError || !document.isObject()) return;
        settings=document.object(); lastSettings=data; invalidate();
    }
public:
    FloatlandDecoration() {
        readSettings();
        timer.setInterval(500);
        connect(&timer,&QTimer::timeout,this,[this]{ readSettings(); });
        timer.start();
    }
    QMargins margins(MarginsType type=Full) const override {
        if(type==ShadowsOnly || (window() && window()->windowStates().testFlag(Qt::WindowFullScreen))) return {};
        return {border,32,border,border};
    }
    void paint(QPaintDevice* device) override {
        // Only a successfully instantiated CSD marks its own window. Failed loading
        // leaves the app ID unchanged, so Floatland's compositor titlebar remains.
        if(!tagged && waylandWindow()->shellSurface()) {
            QString id=QGuiApplication::desktopFileName();
            if(id.isEmpty()) id=QGuiApplication::applicationName();
            if(id.isEmpty()) id="qt-app";
            appId=id+".floatland-csd-"+QUuid::createUuid().toString(QUuid::Id128);
            waylandWindow()->shellSurface()->setAppId(appId);
            tagged=true;
        }
        const double width=waylandWindow()->surfaceSize().width();
        QPainter p(device); p.setRenderHint(QPainter::Antialiasing);
        QColor background=color("titlebar_color","#1b2029");
        background.setAlphaF(settings.value("titlebar_opacity").toDouble(1));
        p.fillRect(QRectF(0,0,width,32),background);
        const auto bounds=Floatland::titleRect(width,left(),order());
        if(settings.value("title_enabled").toBool(true)) {
            p.setPen(color("titlebar_text_color","#edf2ff"));
            QFont font=p.font();font.setPointSize(settings.value("titlebar_font_size").toInt(10));p.setFont(font);
            const auto align=settings.value("title_alignment").toString("left");
            const int alignment=Qt::AlignVCenter|(align=="center"?Qt::AlignHCenter:align=="right"?Qt::AlignRight:Qt::AlignLeft);
            p.drawText(QRectF(bounds.x,0,bounds.w,32),alignment,p.fontMetrics().elidedText(window()->title(),Qt::ElideRight,int(bounds.w)));
        }
        const char* keys[]={"close_color","minimize_color","maximize_color"};
        const char* defaults[]={"#f55c57","#fabe2e","#33c459"};
        for(int i=0;i<3;++i) {
            const auto action=static_cast<Floatland::Control>(i);
            const auto cell=Floatland::buttonRect(width,action,left(),order());
            if(cell.w<=0) continue;
            QColor base=color(keys[i],defaults[i]);
            if(!window()->isActive()) base.setAlphaF(.5);
            if(pressed==action && hovered==action) base=base.lighter(125);
            const QPointF center(cell.x+cell.w/2,16);
            const double radius=pressed==action && hovered==action?7.8:7;
            p.setPen(Qt::NoPen);
            QLinearGradient gradient(center.x(),16-radius,center.x(),16+radius);
            gradient.setColorAt(0,base.lighter(125));gradient.setColorAt(.45,base);gradient.setColorAt(1,base.darker(110));
            if(settings.value("button_texture").toBool(true)) p.setBrush(gradient); else p.setBrush(base);
            p.drawEllipse(center,radius,radius);
            if(!settings.value("button_icons").toBool(true) ||
               (settings.value("button_hover_only").toBool(true) && hovered==Floatland::Control::None)) continue;
            p.setPen(QPen(base.darker(230),1.6,Qt::SolidLine,Qt::RoundCap,Qt::RoundJoin));
            p.setBrush(Qt::NoBrush);
            if(i==0) {
                p.drawLine(center+QPointF(-2.5,-2.5),center+QPointF(2.5,2.5));
                p.drawLine(center+QPointF(-2.5,2.5),center+QPointF(2.5,-2.5));
            } else if(i==1) p.drawLine(center+QPointF(-3,0),center+QPointF(3,0));
            else p.drawRect(QRectF(center.x()-2.5,center.y()-2.5,5,5));
        }
        p.fillRect(QRectF(0,32,border,waylandWindow()->surfaceSize().height()-32),background);
        p.fillRect(QRectF(width-border,32,border,waylandWindow()->surfaceSize().height()-32),background);
        p.fillRect(QRectF(0,waylandWindow()->surfaceSize().height()-border,width,border),background);
    }
    bool handleMouse(QWaylandInputDevice* input,const QPointF& local,const QPointF&,
                     Qt::MouseButtons buttons,Qt::KeyboardModifiers) override {
        const auto next=hit(local);
        if(hovered!=next) { hovered=next; invalidate(); }
        const bool down=isLeftClicked(buttons),up=isLeftReleased(buttons);
        const auto size=waylandWindow()->surfaceSize();
        Qt::Edges edges;
        if(local.x()<border) edges|=Qt::LeftEdge;
        if(local.x()>size.width()-border) edges|=Qt::RightEdge;
        if(local.y()<border) edges|=Qt::TopEdge;
        if(local.y()>size.height()-border) edges|=Qt::BottomEdge;
        const bool owned=pressed!=Floatland::Control::None;
        if(down) {
            pressed=next;
            if(next==Floatland::Control::None) {
                if(edges) startResize(input,edges,buttons);
                else if(local.y()<32) startMove(input,buttons);
            }
            invalidate();
        }
        if(up) {
            const auto action=pressed;
            pressed=Floatland::Control::None; invalidate();
            setMouseButtons(buttons);
            if(action!=Floatland::Control::None && action==next) activate(action);
            return owned || local.y()<32 || bool(edges);
        }
        if(isRightClicked(buttons) && local.y()<32 && next==Floatland::Control::None) showWindowMenu(input);
        setMouseButtons(buttons);
        return owned || local.y()<32 || bool(edges);
    }
    bool handleTouch(QWaylandInputDevice* input,const QPointF& local,const QPointF& global,
                     QEventPoint::State state,Qt::KeyboardModifiers mods) override {
        if(state==QEventPoint::Pressed) return handleMouse(input,local,global,Qt::LeftButton,mods);
        if(state==QEventPoint::Released) return handleMouse(input,local,global,Qt::NoButton,mods);
        return handleMouse(input,local,global,Qt::LeftButton,mods);
    }
};

class FloatlandDecorationPlugin final : public QWaylandDecorationPlugin {
    Q_OBJECT
    Q_PLUGIN_METADATA(IID QWaylandDecorationFactoryInterface_iid FILE "floatland.json")
public:
    QWaylandAbstractDecoration* create(const QString&,const QStringList&) override {
        return new FloatlandDecoration;
    }
};
#include "decoration.moc"
