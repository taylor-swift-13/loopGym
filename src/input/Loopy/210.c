// Source: data/benchmarks/accelerating_invariant_generation/svcomp/terminator_02_true.c
extern int unknown_int(void);
extern int unknown_bool(void);

/*@
  requires x<100;
  requires z<100;
*/
void loopy_210(int x, int y, int z)
{
  
  
  
  
  
  while(x<100 && 100<z) 
  {
    int tmp=unknown_bool();
    if (tmp)
   {
     x++;
   }
   else
   {
     x--;
     z--;
   }
  }                       
    
  {;
//@ assert(x>=100 || z<=100);
}

}
