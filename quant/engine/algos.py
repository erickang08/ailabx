from .common.logging_utils import logger
import pandas as pd
from .technical.cross import *
from .technical.indicators import *

'''
算法基类，是一个可以复用的功能单元。
代码很简单，只一个name属性，以及一个需要子类实现的功能__call__。
'''
class Algo(object):
    def __init__(self, name=None):
        self._name = name

    @property
    def name(self):
        if self._name is None:
            self._name = self.__class__.__name__
        return self._name

    def __call__(self, context):
        raise NotImplementedError("%s 没有实现!" % self.name)

class Strategy(object):

    def __init__(self, algos,name=''):
        self.name = name
        self.algos = algos
        self.check_run_always = any(hasattr(x, 'run_always')
                                    for x in self.algos)

    def __call__(self, context):
        # normal runing mode
        if not self.check_run_always:
            for algo in self.algos:
                if not algo(context):
                    return False
            return True
        # run mode when at least one algo has a run_always attribute
        else:
            # store result in res
            # allows continuation to check for and run
            # algos that have run_always set to True
            res = True
            for algo in self.algos:
                if res:
                    res = algo(context)
                elif hasattr(algo, 'run_always'):
                    if algo.run_always:
                        algo(context)

class PrintBar(Algo):
    def __call__(self, context):
        logger.info('当前索引：{}，当前日期:{}'.format(context['idx'],context['now']))
        return True

class RunOnce(Algo):
    def __init__(self):
        super(RunOnce, self).__init__()
        self.has_run = False

    def __call__(self, context):
        # if it hasn't run then we will
        # run it and set flag
        if not self.has_run:
            self.has_run = True
            return True

        # return false to stop future execution
        return False


class SelectAll(Algo):
    def __init__(self):
        super(SelectAll, self).__init__()

    def __call__(self,context,direction='LONG'):
        context[direction] = context['universe']
        return True

class SelectByExpr(Algo):
    def __init__(self,long_expr,flat_expr):
        self.long_expr = long_expr
        self.flat_expr = flat_expr
        self.run_once = RunOnce()

    def __call__(self, context):
        if self.run_once(context) is True: #运行过了，会访问False表示不用继续，本算法返回True,continue
            codes = context['universe']
            all_close = context['all_close']
            all_data = context['all_data']
            # price_keys= ['open','high','low','close']
            sig = pd.DataFrame(index=all_close.index, columns=all_close.columns)
            for symbol in codes:
                df = all_data[symbol]
                close = df['Close']
                high = df['High']
                low = df['Low']
                open = df['Open']

                long_sig = eval(self.long_expr)  # eval('cross_up(ma(close,5),ma(close,10')
                flat_sig = eval(self.flat_expr)  # eval('cross_down(ma(close,5),ma(close,10)')
                sig[symbol] = long_sig + flat_sig
                context['sig'] = sig
            #print(sig[sig>0])
            return True

        SelectWhere(signal=context['sig'])(context)
        return True

class SelectWhere(Algo):
    def __init__(self, signal):
        self.signal = signal #df:['AAPL':[1,0,-1],'AMZN':[...]]

    def __call__(self, context):

        #这里得到某一天的信号，是一个Series, index = ['AAPL'...]
        day_signal = self.signal.loc[context['now']]

        #LONG or FLAT
        day_signal_long = day_signal[day_signal==1]
        day_signal_flat = day_signal[day_signal == -1]

        #按方向过滤完信号后，取索引就是证券代码列表
        selected = day_signal.index
        context['LONG'] = list(day_signal_long.index)
        context['FLAT'] = list(day_signal_flat.index)

        return True

class WeighEqually(Algo):
    def __init__(self):
        super(WeighEqually, self).__init__()

    def __call__(self, context):
        #FLAT不用权重，这个列表里的都平仓，rebalance会自动处理
        if 'LONG' in context.keys():
            selected = context['LONG']
            n = len(selected)

            if n == 0:
                context['weights'] = {}
            else:
                w = 1.0 / n
                context['weights'] = {x: w for x in selected}

        return True

class Constraint(Algo):
    def __init__(self,params):
        self.params = params

    def __call__(self,context):
        if 'max_weight' in self.params.keys():
            context['max_weight'] = self.params['max_weight']
