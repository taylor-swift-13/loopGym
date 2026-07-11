// Source: data/benchmarks/LinearArbitrary-SeaHorn/pie/hola/43.c

extern int unknown1();
extern int unknown2();
extern int unknown3();

/*@
  requires !(x==y);
*/
void loopy_142(int x, int y)
{
  
  
  int i=0;
  int t=y;
   
  
  
  while (unknown3()){
    if (x > 0)   
      y = y + x;
  }
   
  {;
//@ assert(y>=t);
}

}
