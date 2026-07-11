// Source: data/benchmarks/LinearArbitrary-SeaHorn/pie/hola/01.c

extern int unknown1();

void loopy_117(void)
{
 int x=1; int y=1;
 while(unknown1()) {
   int t1 = x;
   int t2 = y;
   x = t1+ t2;
   y = t1 + t2;
 }
 {;
//@ assert(y>=1);
}

}
